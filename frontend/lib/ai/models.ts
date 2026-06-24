export interface ChatModel {
  id: string;
  name: string;
  description: string;
  provider: string;
}

// Only models that users can select in the UI
export const chatModels: ChatModel[] = [
  {
    id: 'chat-model',
    name: 'Claude Sonnet 4.6',
    description: 'Most capable model for complex tasks',
    provider: 'anthropic',
  },
  {
    id: 'chat-model-reasoning',
    name: 'Claude Haiku 4.5',
    description: 'Fast and efficient for most tasks',
    provider: 'anthropic',
  },
];

export const DEFAULT_CHAT_MODEL = 'chat-model';
export const DEFAULT_MODEL_ID = DEFAULT_CHAT_MODEL;
export const models = chatModels;