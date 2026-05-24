import { useCallback, useState } from "react";
import { abortStream, sendMessageStream } from "@/lib/claude";
import { saveConversation } from "@/lib/storage";
import type {
  Attachment,
  Conversation,
  Message,
  ModelId,
  UsageInfo,
} from "@/lib/types";

const newId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function useChat(initial: Conversation, onPersisted?: () => void) {
  const [conversation, setConversation] = useState<Conversation>(initial);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  const sendMessage = useCallback(
    async (text: string, attachments: Attachment[] = []) => {
      if (streaming) return;
      if (!text.trim() && attachments.length === 0) return;
      setError(null);

      const trimmed = text.trim();
      const userMsg: Message = {
        id: newId(),
        role: "user",
        content: trimmed,
        attachments: attachments.length ? attachments : undefined,
        createdAt: Date.now(),
      };
      const assistantMsg: Message = {
        id: newId(),
        role: "assistant",
        content: "",
        createdAt: Date.now(),
      };

      let snapshot: Conversation | null = null;
      setConversation((c) => {
        const next: Conversation = {
          ...c,
          messages: [...c.messages, userMsg, assistantMsg],
          updatedAt: Date.now(),
        };
        snapshot = next;
        return next;
      });
      if (!snapshot) return;

      setStreaming(true);

      let buffer = "";
      let resolvedSessionId = snapshot!.sessionId;
      let failed = false;

      try {
        await sendMessageStream(
          {
            model: snapshot!.model as ModelId,
            systemPrompt: snapshot!.systemPrompt,
            sessionId: snapshot!.sessionId,
            messages: snapshot!.messages.filter(
              (m) => m.id !== assistantMsg.id
            ),
          },
          (e) => {
            if (e.type === "delta" && e.text) {
              buffer += e.text;
              setConversation((c) => ({
                ...c,
                messages: c.messages.map((m) =>
                  m.id === assistantMsg.id ? { ...m, content: buffer } : m
                ),
              }));
            } else if (e.type === "done") {
              if (e.sessionId) resolvedSessionId = e.sessionId;
              if (e.usage) {
                setUsage({
                  inputTokens: e.usage.input_tokens,
                  outputTokens: e.usage.output_tokens,
                });
              }
            } else if (e.type === "error") {
              failed = true;
              setError(e.error ?? "Bilinmeyen hata");
            }
          }
        );
      } catch (err) {
        failed = true;
        setError(String(err));
      } finally {
        setStreaming(false);
        setConversation((current) => {
          const finalConv: Conversation = {
            ...current,
            title:
              current.title === "Yeni sohbet" && trimmed
                ? trimmed.slice(0, 60)
                : current.title,
            sessionId: resolvedSessionId,
            messages: current.messages.map((m) =>
              m.id === assistantMsg.id ? { ...m, content: buffer } : m
            ),
            updatedAt: Date.now(),
          };
          if (!failed || buffer.length > 0) {
            saveConversation(finalConv)
              .then(() => onPersisted?.())
              .catch(() => {});
          }
          return finalConv;
        });
      }
    },
    [streaming, onPersisted]
  );

  const stop = useCallback(() => {
    abortStream().catch(() => {});
  }, []);

  const setModel = useCallback((model: string) => {
    setConversation((c) => ({ ...c, model }));
  }, []);

  return { conversation, streaming, error, usage, sendMessage, stop, setModel };
}

export function newConversation(model: string): Conversation {
  return {
    id: newId(),
    title: "Yeni sohbet",
    model,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}
