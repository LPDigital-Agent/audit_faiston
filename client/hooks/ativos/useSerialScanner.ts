// =============================================================================
// useSerialScanner Hook - SGA Inventory Module
// =============================================================================
// Mobile serial number scanning with barcode/QR code support.
// Handles camera access, scanning validation, and asset lookup.
// =============================================================================


import { useState, useCallback, useRef, useEffect } from 'react';
import { whereIsSerial } from '@/services/sgaAgentcore';
import type { SGAAsset, SGAMovement } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

type ScanMode = 'barcode' | 'qrcode' | 'manual';

interface ScanResult {
  serial: string;
  timestamp: Date;
  asset: SGAAsset | null;
  timeline: SGAMovement[];
  found: boolean;
}

interface UseSerialScannerReturn {
  // Scanner state
  isScanning: boolean;
  scanMode: ScanMode;
  lastScannedSerial: string | null;
  scanHistory: ScanResult[];

  // Camera state
  hasCameraPermission: boolean | null;
  isCameraActive: boolean;
  cameraError: string | null;

  // Lookup state
  isLookingUp: boolean;
  lookupError: string | null;
  currentResult: ScanResult | null;

  // Actions
  startScanning: (mode?: ScanMode) => Promise<void>;
  stopScanning: () => void;
  processSerial: (serial: string) => Promise<ScanResult>;
  manualEntry: (serial: string) => Promise<ScanResult>;
  clearResult: () => void;
  clearHistory: () => void;

  // Camera ref for video element
  videoRef: React.RefObject<HTMLVideoElement>;
}

// =============================================================================
// Constants
// =============================================================================

const SCAN_HISTORY_KEY = 'sga_scan_history';
const MAX_HISTORY_ITEMS = 50;

// =============================================================================
// Hook
// =============================================================================

export function useSerialScanner(): UseSerialScannerReturn {
  // Scanner state
  const [isScanning, setIsScanning] = useState(false);
  const [scanMode, setScanMode] = useState<ScanMode>('manual');
  const [lastScannedSerial, setLastScannedSerial] = useState<string | null>(null);
  const [scanHistory, setScanHistory] = useState<ScanResult[]>([]);

  // Camera state
  const [hasCameraPermission, setHasCameraPermission] = useState<boolean | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  // Lookup state
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [currentResult, setCurrentResult] = useState<ScanResult | null>(null);

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Load scan history from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SCAN_HISTORY_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert timestamp strings back to Date objects
        const history = parsed.map((item: ScanResult & { timestamp: string }) => ({
          ...item,
          timestamp: new Date(item.timestamp),
        }));
        setScanHistory(history);
      }
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  // Save scan history to localStorage when it changes
  useEffect(() => {
    try {
      localStorage.setItem(SCAN_HISTORY_KEY, JSON.stringify(scanHistory));
    } catch {
      // Ignore localStorage errors
    }
  }, [scanHistory]);

  // Cleanup camera on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  // Check camera permission
  const checkCameraPermission = useCallback(async (): Promise<boolean> => {
    try {
      // Check if navigator.mediaDevices is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError('Camera API not supported in this browser');
        setHasCameraPermission(false);
        return false;
      }

      // Try to get camera stream to check permission
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stream.getTracks().forEach(track => track.stop());
      setHasCameraPermission(true);
      setCameraError(null);
      return true;
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          setCameraError('Camera permission denied');
        } else if (error.name === 'NotFoundError') {
          setCameraError('No camera found');
        } else {
          setCameraError(error.message);
        }
      }
      setHasCameraPermission(false);
      return false;
    }
  }, []);

  // Start camera stream
  const startCamera = useCallback(async (): Promise<boolean> => {
    try {
      if (!videoRef.current) {
        setCameraError('Video element not available');
        return false;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment', // Prefer back camera on mobile
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });

      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();

      setIsCameraActive(true);
      setCameraError(null);
      return true;
    } catch (error) {
      if (error instanceof Error) {
        setCameraError(error.message);
      }
      setIsCameraActive(false);
      return false;
    }
  }, []);

  // Stop camera stream
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  }, []);

  // Process a serial number (lookup asset)
  const processSerial = useCallback(async (serial: string): Promise<ScanResult> => {
    const trimmedSerial = serial.trim().toUpperCase();

    if (!trimmedSerial) {
      throw new Error('Serial number cannot be empty');
    }

    setIsLookingUp(true);
    setLookupError(null);
    setLastScannedSerial(trimmedSerial);

    try {
      const response = await whereIsSerial({ serial_number: trimmedSerial });

      const result: ScanResult = {
        serial: trimmedSerial,
        timestamp: new Date(),
        asset: response.data.asset ?? null,
        timeline: response.data.timeline ?? [],
        found: !!response.data.asset,
      };

      setCurrentResult(result);

      // Add to history (avoid duplicates of same serial in succession)
      setScanHistory(prev => {
        const filtered = prev.filter(item => item.serial !== trimmedSerial);
        const newHistory = [result, ...filtered].slice(0, MAX_HISTORY_ITEMS);
        return newHistory;
      });

      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to lookup serial';
      setLookupError(message);

      // Still create a result entry for not found
      const result: ScanResult = {
        serial: trimmedSerial,
        timestamp: new Date(),
        asset: null,
        timeline: [],
        found: false,
      };

      setCurrentResult(result);
      return result;
    } finally {
      setIsLookingUp(false);
    }
  }, []);

  // Start scanning
  const startScanning = useCallback(async (mode: ScanMode = 'manual') => {
    setScanMode(mode);
    setIsScanning(true);
    setCameraError(null);

    if (mode !== 'manual') {
      const hasPermission = await checkCameraPermission();
      if (hasPermission) {
        await startCamera();
      }
    }
  }, [checkCameraPermission, startCamera]);

  // Stop scanning
  const stopScanning = useCallback(() => {
    setIsScanning(false);
    stopCamera();
  }, [stopCamera]);

  // Manual entry
  const manualEntry = useCallback(async (serial: string): Promise<ScanResult> => {
    return processSerial(serial);
  }, [processSerial]);

  // Clear current result
  const clearResult = useCallback(() => {
    setCurrentResult(null);
    setLastScannedSerial(null);
    setLookupError(null);
  }, []);

  // Clear history
  const clearHistory = useCallback(() => {
    setScanHistory([]);
    try {
      localStorage.removeItem(SCAN_HISTORY_KEY);
    } catch {
      // Ignore
    }
  }, []);

  return {
    // Scanner state
    isScanning,
    scanMode,
    lastScannedSerial,
    scanHistory,

    // Camera state
    hasCameraPermission,
    isCameraActive,
    cameraError,

    // Lookup state
    isLookingUp,
    lookupError,
    currentResult,

    // Actions
    startScanning,
    stopScanning,
    processSerial,
    manualEntry,
    clearResult,
    clearHistory,

    // Camera ref
    videoRef: videoRef as React.RefObject<HTMLVideoElement>,
  };
}

// Re-export types
export type { ScanMode, ScanResult };
