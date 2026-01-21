// =============================================================================
// Zoom Video SDK Type Declarations
// =============================================================================
// Minimal type declarations for @zoom/videosdk to allow dynamic imports.
// The SDK is optional and will be loaded only if available.
// =============================================================================

declare module '@zoom/videosdk' {
  interface ZoomClient {
    init(language: string, dependentAssets: string, options?: { patchJsMedia?: boolean }): Promise<void>;
    join(topic: string, token: string, userName: string, password?: string): Promise<void>;
    leave(): Promise<void>;
    destroy(): void;
    getMediaStream(): ZoomMediaStream;
    on(event: string, callback: (...args: unknown[]) => void): void;
    off(event: string, callback: (...args: unknown[]) => void): void;
  }

  interface ZoomMediaStream {
    startVideo(options?: { videoElement?: HTMLVideoElement }): Promise<void>;
    stopVideo(): Promise<void>;
    startAudio(): Promise<void>;
    stopAudio(): Promise<void>;
    muteAudio(): Promise<void>;
    unmuteAudio(): Promise<void>;
    switchCamera(deviceId: string): Promise<void>;
    switchMicrophone(deviceId: string): Promise<void>;
    isAudioMuted(): boolean;
    isVideoStarted(): boolean;
  }

  interface ZoomVideoDefault {
    createClient(): ZoomClient;
    getDevices(): Promise<MediaDeviceInfo[]>;
    checkSystemRequirements(): { video: boolean; audio: boolean };
  }

  const ZoomVideo: ZoomVideoDefault;
  export default ZoomVideo;
}
