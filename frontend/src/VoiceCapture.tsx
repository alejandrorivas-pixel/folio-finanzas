import { useEffect, useRef, useState } from "react";
import { FileAudio, LoaderCircle, Mic, Square, X } from "lucide-react";
import { api } from "./api";

type Stage = "idle" | "requesting" | "recording" | "transcribing";
const MAX_BYTES = 10 * 1024 * 1024;
const DEMO_DICTATION =
  "Hoy pagué 350 pesos en efectivo a Proveedor Demo por materiales ficticios";

export default function VoiceCapture({
  demoMode,
  aiConfigured,
  disabled,
  onText,
  onActive,
}: {
  demoMode: boolean;
  aiConfigured: boolean;
  disabled: boolean;
  onText: (text: string) => void;
  onActive: (active: boolean) => void;
}) {
  const [stage, setStage] = useState<Stage>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const mounted = useRef(true);
  const audioInput = useRef<HTMLInputElement>(null);
  const onActiveRef = useRef(onActive);
  onActiveRef.current = onActive;

  const release = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  };
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
      controller.current?.abort();
      if (recorder.current?.state === "recording") recorder.current.stop();
      release();
    };
  }, []);
  useEffect(() => {
    onActiveRef.current(stage !== "idle");
  }, [stage]);

  const transcribe = async (file: File, current = ++generation.current) => {
    if (!/\.(mp3|mp4|m4a|wav|webm)$/i.test(file.name)) {
      setError("Usa un audio MP3, MP4, M4A, WAV o WebM de hasta 10 MB.");
      return;
    }
    if (!file.size || file.size > MAX_BYTES) {
      setError(
        file.size
          ? "El audio supera los 10 MB. Graba un mensaje más corto."
          : "No se detectó audio. Intenta grabar otra vez.",
      );
      setStage("idle");
      return;
    }
    setStage("transcribing");
    setError("");
    setNotice("");
    const request = new AbortController();
    controller.current = request;
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await api<{
        text: string;
        model: string;
        language: string;
      }>("/api/audio/transcribe", {
        method: "POST",
        body,
        signal: request.signal,
      });
      if (!mounted.current || current !== generation.current) return;
      if (!result.text.trim())
        throw new Error(
          "No se encontró una frase. Intenta hablar más cerca del micrófono.",
        );
      onText(result.text.trim());
      setNotice(
        "Transcripción lista. Puedes editarla antes de enviarla al agente de captura.",
      );
    } catch (e) {
      if (
        mounted.current &&
        current === generation.current &&
        (e as Error).name !== "AbortError"
      )
        setError((e as Error).message);
    } finally {
      if (mounted.current && current === generation.current) setStage("idle");
      if (controller.current === request) controller.current = null;
      if (audioInput.current) audioInput.current.value = "";
    }
  };
  const cancel = () => {
    generation.current += 1;
    controller.current?.abort();
    if (recorder.current?.state === "recording") recorder.current.stop();
    release();
    setStage("idle");
    setNotice("Dictado cancelado.");
  };
  const start = async () => {
    setError("");
    setNotice("");
    if (demoMode) {
      onText(DEMO_DICTATION);
      setNotice(
        "Ejemplo ficticio insertado. No se grabó audio ni se usó OpenAI. Edita el texto antes de enviarlo.",
      );
      return;
    }
    if (
      !window.isSecureContext ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        "El micrófono requiere HTTPS o localhost y un navegador compatible. También puedes subir un audio o usar el dictado del teclado.",
      );
      return;
    }
    const current = ++generation.current;
    setStage("requesting");
    setSeconds(0);
    try {
      const audio = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current || current !== generation.current) {
        audio.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = audio;
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/webm",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      const recording = new MediaRecorder(
        audio,
        mimeType ? { mimeType } : undefined,
      );
      recorder.current = recording;
      const chunks: Blob[] = [];
      let size = 0;
      recording.ondataavailable = (event) => {
        if (current !== generation.current || !event.data.size) return;
        chunks.push(event.data);
        size += event.data.size;
        if (size > MAX_BYTES) {
          generation.current += 1;
          recording.stop();
          release();
          setStage("idle");
          setError(
            "El audio alcanzó el límite de 10 MB. Intenta un dictado más corto.",
          );
        }
      };
      recording.onerror = () => {
        if (!mounted.current || current !== generation.current) return;
        generation.current += 1;
        release();
        setStage("idle");
        setError(
          "Se interrumpió la grabación. Puedes volver a grabar o subir un audio.",
        );
      };
      recording.onstop = () => {
        if (!mounted.current || current !== generation.current) return;
        release();
        const mime = recording.mimeType || "audio/webm";
        const extension = mime.includes("mp4") ? "m4a" : "webm";
        void transcribe(
          new File(chunks, `dictado.${extension}`, { type: mime }),
          current,
        );
      };
      recording.start(1000);
      setStage("recording");
      const startedAt = Date.now();
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        setSeconds(Math.min(elapsed, 60));
        if (elapsed >= 60 && recording.state === "recording") recording.stop();
      }, 250);
    } catch (e) {
      if (!mounted.current || current !== generation.current) return;
      release();
      setStage("idle");
      setError(
        (e as Error).name === "NotAllowedError"
          ? "No se autorizó el micrófono. Habilítalo en el navegador o usa un archivo de audio."
          : "No se pudo iniciar el micrófono. Revisa que esté disponible o sube un archivo de audio.",
      );
    }
  };
  const active = stage !== "idle";

  return (
    <div className="voice-capture">
      <div className="voice-actions">
        {stage === "idle" ? (
          <>
            <button
              type="button"
              className="voice-button"
              onClick={() => void start()}
              disabled={disabled || (!demoMode && !aiConfigured)}
            >
              <Mic size={15} />
              {demoMode ? "Probar dictado" : "Dictar"}
            </button>
            {!demoMode && (
              <button
                type="button"
                className="voice-button"
                disabled={disabled || !aiConfigured}
                onClick={() => audioInput.current?.click()}
              >
                <FileAudio size={15} />
                Subir audio
              </button>
            )}
          </>
        ) : (
          <>
            <span className="voice-progress" role="status">
              {stage === "recording" ? (
                <>
                  <span className="recording-dot" />
                  {seconds}s / 60s
                </>
              ) : (
                <>
                  <LoaderCircle size={14} className="spin" />
                  {stage === "requesting"
                    ? "Esperando micrófono…"
                    : "Transcribiendo…"}
                </>
              )}
            </span>
            {stage === "recording" && (
              <button
                type="button"
                className="voice-button"
                onClick={() => {
                  if (recorder.current?.state === "recording")
                    recorder.current.stop();
                }}
              >
                <Square size={13} />
                Terminar
              </button>
            )}
            <button
              type="button"
              className="voice-button"
              onClick={cancel}
              aria-label="Cancelar dictado"
            >
              <X size={14} />
              Cancelar
            </button>
          </>
        )}
      </div>
      <input
        ref={audioInput}
        type="file"
        className="sr-only"
        aria-label="Audio para transcribir"
        accept=".mp3,.mp4,.m4a,.wav,.webm,audio/mpeg,audio/mp4,audio/wav,audio/webm"
        disabled={active || demoMode || !aiConfigured}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void transcribe(file);
        }}
      />
      <p className="voice-hint">
        {demoMode
          ? "Demostración sin grabación. También puedes dictar con tu teclado o Wispr Flow."
          : "Grabación: hasta 60 s · Archivos: hasta 10 MB. El audio se envía a OpenAI al terminar; revisa la transcripción antes de enviarla."}
      </p>
      {!demoMode && !aiConfigured && (
        <p className="voice-hint">
          Conecta OpenAI en el backend para activar la transcripción.
        </p>
      )}
      {notice && (
        <p className="voice-notice" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="voice-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
