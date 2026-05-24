import { useCallback, useRef, useState } from "react";
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

export interface PersistEvent {
  isNew: boolean;
  titleChanged: boolean;
}

export function useChat(
  initial: Conversation,
  onPersisted?: (event: PersistEvent) => void
) {
  const [conversation, setConversation] = useState<Conversation>(initial);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  const convRef = useRef(conversation);
  convRef.current = conversation;
  const firstSaveRef = useRef(true);

  const sendMessage = useCallback(
    async (text: string, attachments: Attachment[] = []) => {
      if (streaming) return;
      const trimmed = text.trim();
      if (!trimmed && attachments.length === 0) return;
      setError(null);

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

      const baseConv = convRef.current;
      const messagesForApi = [...baseConv.messages, userMsg];

      setConversation((c) => ({
        ...c,
        messages: [...c.messages, userMsg, assistantMsg],
        updatedAt: Date.now(),
      }));

      setStreaming(true);

      let buffer = "";
      let resolvedSessionId = baseConv.sessionId;
      let failed = false;

      try {
        await sendMessageStream(
          {
            model: baseConv.model as ModelId,
            systemPrompt: baseConv.systemPrompt,
            sessionId: baseConv.sessionId,
            messages: messagesForApi,
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
          const oldTitle = current.title;
          const newTitle =
            oldTitle === "Yeni sohbet" && trimmed
              ? trimmed.slice(0, 60)
              : oldTitle;
          const finalConv: Conversation = {
            ...current,
            title: newTitle,
            sessionId: resolvedSessionId,
            messages: current.messages.map((m) =>
              m.id === assistantMsg.id ? { ...m, content: buffer } : m
            ),
            updatedAt: Date.now(),
          };
          if (!failed || buffer.length > 0) {
            const isNew = firstSaveRef.current;
            const titleChanged = newTitle !== oldTitle;
            firstSaveRef.current = false;
            saveConversation(finalConv)
              .then(() => onPersisted?.({ isNew, titleChanged }))
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

  const setSystemPrompt = useCallback((systemPrompt: string) => {
    setConversation((c) => ({
      ...c,
      systemPrompt: systemPrompt.trim() ? systemPrompt : undefined,
    }));
  }, []);

  return {
    conversation,
    streaming,
    error,
    usage,
    sendMessage,
    stop,
    setModel,
    setSystemPrompt,
  };
}

export function newConversation(model: string, systemPrompt?: string): Conversation {
  return {
    id: newId(),
    title: "Yeni sohbet",
    model,
    systemPrompt,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}
