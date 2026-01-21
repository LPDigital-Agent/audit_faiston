'use client';

// =============================================================================
// Mobile Scanner - SGA Inventory PWA Component
// =============================================================================
// Barcode and QR code scanner for mobile devices.
// Uses device camera for real-time scanning of serial numbers and barcodes.
// =============================================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Camera,
  ScanLine,
  X,
  Flashlight,
  FlashlightOff,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Keyboard,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

// =============================================================================
// Types
// =============================================================================

export type ScanType = 'serial' | 'barcode' | 'qrcode' | 'any';

export interface ScanResult {
  value: string;
  type: ScanType;
  timestamp: Date;
  confidence?: number;
}

interface MobileScannerProps {
  onScan: (result: ScanResult) => void;
  scanType?: ScanType;
  placeholder?: string;
  autoFocus?: boolean;
  showManualEntry?: boolean;
  onClose?: () => void;
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

export function MobileScanner({
  onScan,
  scanType = 'any',
  placeholder = 'Escaneie ou digite o codigo...',
  autoFocus = true,
  showManualEntry = true,
  onClose,
  className = '',
}: MobileScannerProps) {
  // State
  const [mode, setMode] = useState<'camera' | 'manual'>('manual');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [flashOn, setFlashOn] = useState(false);
  const [manualInput, setManualInput] = useState('');
  const [lastScan, setLastScan] = useState<ScanResult | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Start camera
  const startCamera = useCallback(async () => {
    setCameraError(null);
    setIsScanning(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment', // Back camera
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      console.error('Camera error:', err);
      setCameraError(
        'Nao foi possivel acessar a camera. Verifique as permissoes.'
      );
      setMode('manual');
    } finally {
      setIsScanning(false);
    }
  }, []);

  // Stop camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  // Toggle flash
  const toggleFlash = useCallback(async () => {
    if (!streamRef.current) return;

    const track = streamRef.current.getVideoTracks()[0];
    if (track && 'getCapabilities' in track) {
      const capabilities = track.getCapabilities() as MediaTrackCapabilities & {
        torch?: boolean;
      };
      if (capabilities.torch) {
        await track.applyConstraints({
          advanced: [{ torch: !flashOn } as MediaTrackConstraintSet],
        });
        setFlashOn(!flashOn);
      }
    }
  }, [flashOn]);

  // Handle mode change
  useEffect(() => {
    if (mode === 'camera') {
      startCamera();
    } else {
      stopCamera();
      if (autoFocus && inputRef.current) {
        inputRef.current.focus();
      }
    }

    return () => {
      stopCamera();
    };
  }, [mode, startCamera, stopCamera, autoFocus]);

  // Handle manual submit
  const handleManualSubmit = useCallback(() => {
    if (!manualInput.trim()) return;

    const result: ScanResult = {
      value: manualInput.trim(),
      type: scanType,
      timestamp: new Date(),
      confidence: 1,
    };

    setLastScan(result);
    onScan(result);
    setManualInput('');
  }, [manualInput, scanType, onScan]);

  // Handle key press
  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleManualSubmit();
      }
    },
    [handleManualSubmit]
  );

  // Simulated scan for demo (in production, use barcode scanning library)
  const handleSimulatedScan = useCallback(() => {
    // This would be replaced with actual barcode detection
    const demoSerial = `SN${Date.now().toString().slice(-8)}`;
    const result: ScanResult = {
      value: demoSerial,
      type: 'serial',
      timestamp: new Date(),
      confidence: 0.95,
    };

    setLastScan(result);
    onScan(result);
  }, [onScan]);

  return (
    <div
      className={`bg-background rounded-xl border border-border overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-full bg-magenta-mid/20">
            <ScanLine className="w-5 h-5 text-magenta-mid" />
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">Scanner</h3>
            <p className="text-xs text-text-muted">
              {scanType === 'serial'
                ? 'Serial Number'
                : scanType === 'barcode'
                  ? 'Codigo de Barras'
                  : 'Qualquer codigo'}
            </p>
          </div>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Mode Toggle */}
      <div className="flex gap-2 p-4 border-b border-border">
        <Button
          variant={mode === 'camera' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setMode('camera')}
          className={
            mode === 'camera' ? 'bg-magenta-mid hover:bg-magenta-mid/90' : ''
          }
        >
          <Camera className="w-4 h-4 mr-2" />
          Camera
        </Button>
        {showManualEntry && (
          <Button
            variant={mode === 'manual' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setMode('manual')}
            className={
              mode === 'manual' ? 'bg-magenta-mid hover:bg-magenta-mid/90' : ''
            }
          >
            <Keyboard className="w-4 h-4 mr-2" />
            Manual
          </Button>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <AnimatePresence mode="wait">
          {mode === 'camera' ? (
            <motion.div
              key="camera"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {cameraError ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <AlertTriangle className="w-12 h-12 text-yellow-400 mb-3" />
                  <p className="text-sm text-text-muted">{cameraError}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={startCamera}
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Tentar novamente
                  </Button>
                </div>
              ) : (
                <div className="relative aspect-[4/3] bg-black rounded-lg overflow-hidden">
                  <video
                    ref={videoRef}
                    className="w-full h-full object-cover"
                    playsInline
                    muted
                  />

                  {/* Scan overlay */}
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="w-64 h-32 border-2 border-magenta-mid rounded-lg relative">
                      <div className="absolute -top-1 -left-1 w-4 h-4 border-t-2 border-l-2 border-magenta-light" />
                      <div className="absolute -top-1 -right-1 w-4 h-4 border-t-2 border-r-2 border-magenta-light" />
                      <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-2 border-l-2 border-magenta-light" />
                      <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-2 border-r-2 border-magenta-light" />

                      {/* Scanning line animation */}
                      <motion.div
                        className="absolute left-0 right-0 h-0.5 bg-magenta-light"
                        initial={{ top: '10%' }}
                        animate={{ top: ['10%', '90%', '10%'] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    </div>
                  </div>

                  {/* Camera controls */}
                  <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-4">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="bg-black/50 text-white"
                      onClick={toggleFlash}
                    >
                      {flashOn ? (
                        <FlashlightOff className="w-5 h-5" />
                      ) : (
                        <Flashlight className="w-5 h-5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="bg-black/50 text-white"
                      onClick={handleSimulatedScan}
                    >
                      <Camera className="w-5 h-5" />
                    </Button>
                  </div>

                  {/* Loading */}
                  {isScanning && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                      <Loader2 className="w-8 h-8 text-magenta-mid animate-spin" />
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="manual"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    ref={inputRef}
                    type="text"
                    placeholder={placeholder}
                    value={manualInput}
                    onChange={(e) => setManualInput(e.target.value)}
                    onKeyDown={handleKeyPress}
                    className="flex-1 bg-white/5 border-border text-lg py-6"
                    autoFocus={autoFocus}
                  />
                  <Button
                    onClick={handleManualSubmit}
                    disabled={!manualInput.trim()}
                    className="h-auto px-6 bg-gradient-to-r from-magenta-mid to-blue-mid"
                  >
                    <CheckCircle2 className="w-5 h-5" />
                  </Button>
                </div>

                <p className="text-xs text-text-muted text-center">
                  Digite o codigo e pressione Enter ou clique no botao
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Last Scan */}
      {lastScan && (
        <div className="p-4 border-t border-border bg-green-500/10">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-green-400">
                Escaneado com sucesso
              </p>
              <p className="text-xs text-text-muted">{lastScan.value}</p>
            </div>
            <Badge variant="outline" className="text-xs">
              {lastScan.type}
            </Badge>
          </div>
        </div>
      )}
    </div>
  );
}
