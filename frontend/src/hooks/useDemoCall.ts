import { useCallback, useEffect, useRef } from 'react';
import { useDemoCallStore } from '../store/demoCallStore';
import { api } from '../services/api';
import type { Agent, PipelineState, StartCallRequest, CallEndData } from '../types';

export function useDemoCall() {
  const {
    sessionId,
    isActive,
    isConnecting,
    pipelineState,
    transcript,
    audioLevel,
    callDuration,
    error,
    setConnecting,
    setActive,
    setSessionId,
    setPipelineState,
    addTranscript,
    setAudioLevel,
    setCallDuration,
    setError,
    setMediaStream,
    setAudioContext,
    setProcessor,
    setWebSocket,
    reset,
    handleCallEnd,
  } = useDemoCallStore();

  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  const durationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const playNext = useCallback(async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      return;
    }
    isPlayingRef.current = true;
    const buffer = audioQueueRef.current.shift()!;

    if (!playbackContextRef.current) {
      playbackContextRef.current = new AudioContext({ sampleRate: 16000 });
    }

    const int16 = new Int16Array(buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0;
    }

    const audioBuffer = playbackContextRef.current.createBuffer(1, float32.length, 16000);
    audioBuffer.copyToChannel(float32, 0);

    const source = playbackContextRef.current.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackContextRef.current.destination);
    source.onended = () => playNext();
    source.start();
  }, []);

  const playAudio = useCallback((arrayBuffer: ArrayBuffer) => {
    audioQueueRef.current.push(arrayBuffer);
    if (!isPlayingRef.current) playNext();
  }, [playNext]);

  const startCall = useCallback(async (agent: Agent) => {
    setConnecting(true);
    setError(null);

    try {
      // Get microphone access
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMediaStream(mediaStream);

      // Setup audio processing for microphone input
      const audioContext = new AudioContext({ sampleRate: 16000 });
      setAudioContext(audioContext);

      const source = audioContext.createMediaStreamSource(mediaStream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      setProcessor(processor);

      // Start call via API
      const requestData: StartCallRequest = {
        agent_id: agent.id,
        direction: agent.direction,
        system_prompt: agent.system_prompt || '',
        opening_line: agent.opening_line || '',
        objective_prompt: agent.objective_prompt || '',
        objection_handling_prompt: agent.objection_handling_prompt || '',
        voicemail_prompt: agent.voicemail_prompt || '',
        closing_prompt: agent.closing_prompt || '',
        escalation_rule: agent.escalation_rule || '',
        greeting_prompt: agent.greeting_prompt || '',
        qualification_prompt: agent.qualification_prompt || '',
        knowledge_prompt: agent.knowledge_prompt || '',
        fallback_prompt: agent.fallback_prompt || '',
        handoff_prompt: agent.handoff_prompt || '',
        interruption_sensitivity: agent.interruption_sensitivity,
        max_call_duration_s: agent.max_call_duration_s,
        silence_timeout_s: agent.silence_timeout_s,
        language: agent.language,
        stt_engine: agent.stt_engine,
        tts_engine: agent.tts_engine,
        tts_voice: agent.tts_voice,
        llm_provider: agent.llm_provider,
        llm_model: agent.llm_model,
        // Stack B fields
        voice_stack: agent.voice_stack || 'stack_a',
        chatterbox_voice: agent.chatterbox_voice || 'Chatterbox-Multilingual.en-US.Female',
        chatterbox_emotion_exaggeration: agent.chatterbox_emotion_exaggeration || 0.5,
        riva_asr_language: agent.riva_asr_language || 'en-US',
        riva_vad_threshold: agent.riva_vad_threshold || 0.5,
      };

      const response = await api.startDemoCall(requestData);
      const { session_id, ws_url } = response;

      setSessionId(session_id);

      // Connect WebSocket for audio
      // In production through nginx, use the same origin; in dev, use VITE_WS_URL
      const isProduction = window.location.protocol === 'https:' || window.location.port === '80' || window.location.port === '443';
      const wsBaseUrl = isProduction
        ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
        : (import.meta.env.VITE_WS_URL || 'ws://localhost:8001');
      const ws = new WebSocket(`${wsBaseUrl}${ws_url}`);
      ws.binaryType = 'arraybuffer';
      setWebSocket(ws);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnecting(false);
        setActive(true);
        setPipelineState('listening');
        startTimeRef.current = Date.now();

        // Start duration timer
        durationIntervalRef.current = window.setInterval(() => {
          setCallDuration((Date.now() - startTimeRef.current) / 1000);
        }, 1000);

        // Connect audio processing
        processor.onaudioprocess = (e) => {
          if (!isActive || ws.readyState !== WebSocket.OPEN) return;
          const inputData = e.inputBuffer.getChannelData(0);
          const int16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }
          // Update visual meter
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) sum += inputData[i] * inputData[i];
          const rms = Math.sqrt(sum / inputData.length);
          setAudioLevel(Math.min(100, rms * 200));
          // Send audio
          ws.send(int16.buffer);
        };

        source.connect(processor);
        processor.connect(audioContext.destination);
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Incoming audio from TTS
          playAudio(event.data);
        } else {
          // Control message
          try {
            const msg = JSON.parse(event.data);
            switch (msg.type) {
              case 'transcript':
                addTranscript(msg.data);
                break;
              case 'state':
                setPipelineState(msg.data as PipelineState);
                break;
              case 'end':
                handleCallEnd(msg.data as CallEndData);
                break;
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
          }
        }
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        cleanup();
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('Connection error');
        cleanup();
      };
    } catch (err) {
      console.error('Start call error:', err);
      setError(err instanceof Error ? err.message : 'Failed to start call');
      setConnecting(false);
      cleanup();
    }
  }, [
    setConnecting,
    setActive,
    setSessionId,
    setPipelineState,
    setMediaStream,
    setAudioContext,
    setProcessor,
    setWebSocket,
    setError,
    setAudioLevel,
    setCallDuration,
    addTranscript,
    handleCallEnd,
    isActive,
    playAudio,
  ]);

  const endCall = useCallback(async () => {
    const { websocket, sessionId: currentSessionId } = useDemoCallStore.getState();
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({ type: 'end' }));
      websocket.close();
    }
    if (currentSessionId) {
      try {
        await api.endDemoCall(currentSessionId);
      } catch (e) {
        console.error('Failed to end call via API:', e);
      }
    }
    cleanup();
  }, []);

  const cleanup = useCallback(() => {
    const {
      mediaStream,
      audioContext,
      processor,
      websocket,
    } = useDemoCallStore.getState();

    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }

    if (processor) {
      processor.disconnect();
    }
    if (audioContext) {
      audioContext.close();
    }
    if (playbackContextRef.current) {
      playbackContextRef.current.close();
      playbackContextRef.current = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
    }
    if (websocket) {
      websocket.onclose = null;
      websocket.onerror = null;
      websocket.onmessage = null;
    }

    audioQueueRef.current = [];
    isPlayingRef.current = false;

    reset();
  }, [reset]);

  // Cleanup on unmount
  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  return {
    sessionId,
    isActive,
    isConnecting,
    pipelineState,
    transcript,
    audioLevel,
    callDuration,
    error,
    startCall,
    endCall,
    cleanup,
  };
}