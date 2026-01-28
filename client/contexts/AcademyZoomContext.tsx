// =============================================================================
// Academy Zoom Context - Faiston Academy
// =============================================================================
// Manages Zoom Video SDK client, session state, and participant management.
// For live classes feature.
//
// Features:
// - Session join/leave management
// - Participant tracking with video/audio states
// - Camera/microphone toggle controls
// - Device selection for video/audio inputs
// - Demo mode fallback when SDK unavailable
//
// Note: Zoom SDK must be installed separately (@zoom/videosdk)
// If not installed, demo mode is used automatically.
//
// Reference: https://developers.zoom.us/docs/video-sdk/web/
// =============================================================================

'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  PropsWithChildren,
} from 'react';

// =============================================================================
// Types
// =============================================================================

export interface Participant {
  oderId: number;
  userId: number;
  displayName: string;
  isVideoOn: boolean;
  isAudioOn: boolean;
  isHost: boolean;
  isSelf: boolean;
  avatar?: string;
}

export interface DeviceInfo {
  deviceId: string;
  label: string;
}

interface AcademyZoomContextType {
  // Client & Stream
  client: unknown | null;
  stream: unknown | null;
  isInitialized: boolean;

  // Session State
  isJoined: boolean;
  isJoining: boolean;
  isDemoMode: boolean;
  sessionName: string | null;

  // Participants
  participants: Participant[];
  localUser: Participant | null;

  // Local Controls
  isVideoOn: boolean;
  isAudioOn: boolean;
  isHandRaised: boolean;

  // Devices
  cameras: DeviceInfo[];
  microphones: DeviceInfo[];
  speakers: DeviceInfo[];
  selectedCamera: string | null;
  selectedMicrophone: string | null;
  selectedSpeaker: string | null;

  // Actions
  initClient: () => Promise<void>;
  joinSession: (token: string, sessionName: string, userName: string) => Promise<void>;
  leaveSession: () => Promise<void>;
  toggleVideo: () => Promise<void>;
  toggleAudio: () => Promise<void>;
  toggleHandRaise: () => void;
  selectCamera: (deviceId: string) => Promise<void>;
  selectMicrophone: (deviceId: string) => Promise<void>;
  selectSpeaker: (deviceId: string) => Promise<void>;
  startVideoPreview: (container: HTMLElement) => Promise<void>;
  stopVideoPreview: () => void;

  // Errors
  error: string | null;
  clearError: () => void;
}

// =============================================================================
// Demo Mode Mock Data
// =============================================================================

const DEMO_INSTRUCTOR: Participant = {
  oderId: 1,
  userId: 1,
  displayName: 'Dr. Roberto Silva',
  isVideoOn: true,
  isAudioOn: true,
  isHost: true,
  isSelf: false,
  avatar: '/avatars/instructor-roberto.svg',
};

const DEMO_PARTICIPANTS: Participant[] = [
  {
    oderId: 2,
    userId: 2,
    displayName: 'Ana Costa',
    isVideoOn: true,
    isAudioOn: false,
    isHost: false,
    isSelf: false,
  },
  {
    oderId: 3,
    userId: 3,
    displayName: 'Carlos Mendes',
    isVideoOn: true,
    isAudioOn: false,
    isHost: false,
    isSelf: false,
  },
  {
    oderId: 4,
    userId: 4,
    displayName: 'Mariana Silva',
    isVideoOn: true,
    isAudioOn: true,
    isHost: false,
    isSelf: false,
  },
  {
    oderId: 5,
    userId: 5,
    displayName: 'Pedro Oliveira',
    isVideoOn: false,
    isAudioOn: true,
    isHost: false,
    isSelf: false,
  },
  {
    oderId: 6,
    userId: 6,
    displayName: 'Julia Santos',
    isVideoOn: true,
    isAudioOn: false,
    isHost: false,
    isSelf: false,
  },
  {
    oderId: 7,
    userId: 7,
    displayName: 'Lucas Ferreira',
    isVideoOn: true,
    isAudioOn: false,
    isHost: false,
    isSelf: false,
  },
];

// =============================================================================
// Context
// =============================================================================

const AcademyZoomContext = createContext<AcademyZoomContextType | null>(null);

// =============================================================================
// Provider
// =============================================================================

interface AcademyZoomProviderProps extends PropsWithChildren {
  sessionId: string;
}

export function AcademyZoomProvider({ children }: AcademyZoomProviderProps) {
  // Refs for SDK instances
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const clientRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const streamRef = useRef<any>(null);
  const previewVideoRef = useRef<HTMLVideoElement | null>(null);

  // Client State
  const [isInitialized, setIsInitialized] = useState(false);
  const [isJoined, setIsJoined] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [sessionName, setSessionName] = useState<string | null>(null);

  // Participants
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [localUser, setLocalUser] = useState<Participant | null>(null);

  // Local Controls
  const [isVideoOn, setIsVideoOn] = useState(false);
  const [isAudioOn, setIsAudioOn] = useState(false);
  const [isHandRaised, setIsHandRaised] = useState(false);

  // Devices
  const [cameras, setCameras] = useState<DeviceInfo[]>([]);
  const [microphones, setMicrophones] = useState<DeviceInfo[]>([]);
  const [speakers, setSpeakers] = useState<DeviceInfo[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null);
  const [selectedMicrophone, setSelectedMicrophone] = useState<string | null>(null);
  const [selectedSpeaker, setSelectedSpeaker] = useState<string | null>(null);

  // Error State
  const [error, setError] = useState<string | null>(null);

  // ==========================================================================
  // Helper: Activate Demo Mode
  // ==========================================================================
  const activateDemoMode = useCallback((sessionNameParam: string, userName: string) => {
    console.log('[AcademyZoomContext] Activating DEMO MODE with mock participants');

    const demoLocalUser: Participant = {
      oderId: 100,
      userId: 100,
      displayName: userName,
      isVideoOn: true,
      isAudioOn: false,
      isHost: false,
      isSelf: true,
    };

    const allParticipants = [DEMO_INSTRUCTOR, ...DEMO_PARTICIPANTS, demoLocalUser];

    setParticipants(allParticipants);
    setLocalUser(demoLocalUser);
    setSessionName(sessionNameParam);
    setIsJoined(true);
    setIsDemoMode(true);
    setError('Demo mode: Zoom connection unavailable');
  }, []);

  // ==========================================================================
  // Initialize Client (attempts to load Zoom SDK dynamically)
  // ==========================================================================
  const initClient = useCallback(async () => {
    if (clientRef.current) {
      return;
    }

    try {
      // Try to dynamically import Zoom SDK
      const ZoomVideo = await import('@zoom/videosdk').catch(() => null);

      if (!ZoomVideo) {
        console.warn('[AcademyZoomContext] Zoom SDK not available, demo mode will be used');
        setIsInitialized(true);
        return;
      }

      const client = ZoomVideo.default.createClient();
      await client.init('en-US', 'Global', { patchJsMedia: true });

      clientRef.current = client;
      setIsInitialized(true);

      // Get available devices
      const devices = await ZoomVideo.default.getDevices();

      const cameraList: DeviceInfo[] = devices
        .filter((d: MediaDeviceInfo) => d.kind === 'videoinput')
        .map((d: MediaDeviceInfo) => ({ deviceId: d.deviceId, label: d.label || 'Camera' }));

      const micList: DeviceInfo[] = devices
        .filter((d: MediaDeviceInfo) => d.kind === 'audioinput')
        .map((d: MediaDeviceInfo) => ({ deviceId: d.deviceId, label: d.label || 'Microphone' }));

      const speakerList: DeviceInfo[] = devices
        .filter((d: MediaDeviceInfo) => d.kind === 'audiooutput')
        .map((d: MediaDeviceInfo) => ({ deviceId: d.deviceId, label: d.label || 'Speaker' }));

      setCameras(cameraList);
      setMicrophones(micList);
      setSpeakers(speakerList);

      if (cameraList.length > 0) setSelectedCamera(cameraList[0].deviceId);
      if (micList.length > 0) setSelectedMicrophone(micList[0].deviceId);
      if (speakerList.length > 0) setSelectedSpeaker(speakerList[0].deviceId);

      console.log('[AcademyZoomContext] Client initialized', {
        cameras: cameraList.length,
        mics: micList.length,
        speakers: speakerList.length,
      });
    } catch (err) {
      console.error('[AcademyZoomContext] Failed to initialize client:', err);
      setError(err instanceof Error ? err.message : 'Failed to initialize Zoom client');
      setIsInitialized(true); // Mark as initialized to enable demo mode
    }
  }, []);

  // ==========================================================================
  // Join Session
  // ==========================================================================
  const joinSession = useCallback(
    async (token: string, name: string, userName: string) => {
      if (isJoining || isJoined) {
        return;
      }

      setIsJoining(true);
      setError(null);

      // If client not initialized or failed, activate demo mode
      if (!clientRef.current) {
        console.log('[AcademyZoomContext] Client not initialized - activating DEMO MODE');
        activateDemoMode(name, userName);
        setIsJoining(false);
        return;
      }

      try {
        await clientRef.current.join(name, token, userName);

        const stream = clientRef.current.getMediaStream();
        streamRef.current = stream;

        setSessionName(name);
        setIsJoined(true);

        const selfId = clientRef.current.getCurrentUserInfo()?.oderId;
        const zoomParticipants = clientRef.current.getAllUser();

        const mappedParticipants = zoomParticipants.map(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (p: any): Participant => ({
            oderId: p.oderId,
            userId: p.userId,
            displayName: p.displayName || 'Participante',
            isVideoOn: p.bVideoOn || false,
            isAudioOn: !p.muted,
            isHost: p.isHost || false,
            isSelf: p.userId === selfId,
          })
        );

        setParticipants(mappedParticipants);
        const self = mappedParticipants.find((p: Participant) => p.isSelf);
        setLocalUser(self || null);

        console.log('[AcademyZoomContext] Joined session:', name);

        try {
          await stream.startAudio();
        } catch (audioErr) {
          console.warn('[AcademyZoomContext] Could not start audio:', audioErr);
        }
      } catch (err) {
        console.error('[AcademyZoomContext] Failed to join session:', err);
        activateDemoMode(name, userName);
      } finally {
        setIsJoining(false);
      }
    },
    [isJoining, isJoined, activateDemoMode]
  );

  // ==========================================================================
  // Leave Session
  // ==========================================================================
  const leaveSession = useCallback(async () => {
    if (isDemoMode) {
      // Reset demo state
      setIsJoined(false);
      setSessionName(null);
      setParticipants([]);
      setLocalUser(null);
      setIsVideoOn(false);
      setIsAudioOn(false);
      setIsHandRaised(false);
      setIsDemoMode(false);
      setError(null);
      return;
    }

    if (!clientRef.current || !isJoined) {
      return;
    }

    try {
      if (streamRef.current) {
        if (isVideoOn) {
          await streamRef.current.stopVideo();
        }
        if (isAudioOn) {
          await streamRef.current.muteAudio();
        }
      }

      await clientRef.current.leave();

      streamRef.current = null;
      setIsJoined(false);
      setSessionName(null);
      setParticipants([]);
      setLocalUser(null);
      setIsVideoOn(false);
      setIsAudioOn(false);
      setIsHandRaised(false);

      console.log('[AcademyZoomContext] Left session');
    } catch (err) {
      console.error('[AcademyZoomContext] Failed to leave session:', err);
      setError(err instanceof Error ? err.message : 'Failed to leave session');
    }
  }, [isJoined, isDemoMode, isVideoOn, isAudioOn]);

  // ==========================================================================
  // Toggle Video
  // ==========================================================================
  const toggleVideo = useCallback(async () => {
    if (isDemoMode) {
      setIsVideoOn((prev) => !prev);
      setLocalUser((prev) => (prev ? { ...prev, isVideoOn: !prev.isVideoOn } : null));
      return;
    }

    if (!streamRef.current) return;

    try {
      if (isVideoOn) {
        await streamRef.current.stopVideo();
        setIsVideoOn(false);
      } else {
        await streamRef.current.startVideo({
          cameraId: selectedCamera || undefined,
          virtualBackground: { imageUrl: 'blur' },
        });
        setIsVideoOn(true);
      }
    } catch (err) {
      console.error('[AcademyZoomContext] Toggle video error:', err);
      setError(err instanceof Error ? err.message : 'Failed to toggle video');
    }
  }, [isDemoMode, isVideoOn, selectedCamera]);

  // ==========================================================================
  // Toggle Audio
  // ==========================================================================
  const toggleAudio = useCallback(async () => {
    if (isDemoMode) {
      setIsAudioOn((prev) => !prev);
      setLocalUser((prev) => (prev ? { ...prev, isAudioOn: !prev.isAudioOn } : null));
      return;
    }

    if (!streamRef.current) return;

    try {
      if (isAudioOn) {
        await streamRef.current.muteAudio();
        setIsAudioOn(false);
      } else {
        await streamRef.current.unmuteAudio();
        setIsAudioOn(true);
      }
    } catch (err) {
      console.error('[AcademyZoomContext] Toggle audio error:', err);
      setError(err instanceof Error ? err.message : 'Failed to toggle audio');
    }
  }, [isDemoMode, isAudioOn]);

  // ==========================================================================
  // Toggle Hand Raise
  // ==========================================================================
  const toggleHandRaise = useCallback(() => {
    setIsHandRaised((prev) => !prev);
  }, []);

  // ==========================================================================
  // Device Selection
  // ==========================================================================
  const selectCamera = useCallback(
    async (deviceId: string) => {
      setSelectedCamera(deviceId);
      if (streamRef.current && isVideoOn && !isDemoMode) {
        try {
          await streamRef.current.switchCamera(deviceId);
        } catch (err) {
          console.error('[AcademyZoomContext] Switch camera error:', err);
        }
      }
    },
    [isVideoOn, isDemoMode]
  );

  const selectMicrophone = useCallback(
    async (deviceId: string) => {
      setSelectedMicrophone(deviceId);
      if (streamRef.current && !isDemoMode) {
        try {
          await streamRef.current.switchMicrophone(deviceId);
        } catch (err) {
          console.error('[AcademyZoomContext] Switch mic error:', err);
        }
      }
    },
    [isDemoMode]
  );

  const selectSpeaker = useCallback(
    async (deviceId: string) => {
      setSelectedSpeaker(deviceId);
      if (streamRef.current && !isDemoMode) {
        try {
          await streamRef.current.switchSpeaker(deviceId);
        } catch (err) {
          console.error('[AcademyZoomContext] Switch speaker error:', err);
        }
      }
    },
    [isDemoMode]
  );

  // ==========================================================================
  // Video Preview
  // ==========================================================================
  const startVideoPreview = useCallback(
    async (container: HTMLElement) => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { deviceId: selectedCamera || undefined },
          audio: false,
        });

        const videoEl = document.createElement('video');
        videoEl.srcObject = stream;
        videoEl.autoplay = true;
        videoEl.muted = true;
        videoEl.playsInline = true;
        videoEl.style.width = '100%';
        videoEl.style.height = '100%';
        videoEl.style.objectFit = 'cover';
        videoEl.style.transform = 'scaleX(-1)';

        container.innerHTML = '';
        container.appendChild(videoEl);
        previewVideoRef.current = videoEl;
      } catch (err) {
        console.error('[AcademyZoomContext] Preview error:', err);
        setError('Nao foi possivel acessar a camera');
      }
    },
    [selectedCamera]
  );

  const stopVideoPreview = useCallback(() => {
    if (previewVideoRef.current) {
      const stream = previewVideoRef.current.srcObject as MediaStream;
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
      previewVideoRef.current.remove();
      previewVideoRef.current = null;
    }
  }, []);

  // ==========================================================================
  // Cleanup on unmount
  // ==========================================================================
  useEffect(() => {
    return () => {
      stopVideoPreview();

      if (clientRef.current && !isDemoMode) {
        if (isJoined) {
          clientRef.current.leave().catch(() => {});
        }
        if (typeof clientRef.current.destroy === 'function') {
          clientRef.current.destroy();
        }
        clientRef.current = null;
      }
    };
  }, [isJoined, isDemoMode, stopVideoPreview]);

  // ==========================================================================
  // Clear Error
  // ==========================================================================
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // ==========================================================================
  // Context Value
  // ==========================================================================
  const value: AcademyZoomContextType = {
    client: clientRef.current,
    stream: streamRef.current,
    isInitialized,
    isJoined,
    isJoining,
    isDemoMode,
    sessionName,
    participants,
    localUser,
    isVideoOn,
    isAudioOn,
    isHandRaised,
    cameras,
    microphones,
    speakers,
    selectedCamera,
    selectedMicrophone,
    selectedSpeaker,
    initClient,
    joinSession,
    leaveSession,
    toggleVideo,
    toggleAudio,
    toggleHandRaise,
    selectCamera,
    selectMicrophone,
    selectSpeaker,
    startVideoPreview,
    stopVideoPreview,
    error,
    clearError,
  };

  return (
    <AcademyZoomContext value={value}>{children}</AcademyZoomContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useAcademyZoom() {
  const context = useContext(AcademyZoomContext);
  if (!context) {
    throw new Error('useAcademyZoom must be used within an AcademyZoomProvider');
  }
  return context;
}
