import { anthropic } from "@ai-sdk/anthropic";
import {
  customProvider,
  extractReasoningMiddleware,
  wrapLanguageModel,
} from "ai";
import { isTestEnvironment } from "../constants";

export const myProvider = isTestEnvironment
  ? (() => {
      const {
        artifactModel,
        chatModel,
        reasoningModel,
        titleModel,
      } = require("./models.mock");
      return customProvider({
        languageModels: {
          "chat-model": chatModel,
          "chat-model-reasoning": reasoningModel,
          "title-model": titleModel,
          "artifact-model": artifactModel,
        },
      });
    })()
  : customProvider({
      languageModels: {
        // Main chat model
        "chat-model": anthropic("claude-sonnet-4-6"),
        
        // Reasoning model
        "chat-model-reasoning": anthropic("claude-haiku-4-5-20251001"),
        
        // Title generation
        "title-model": anthropic("claude-haiku-4-5-20251001"),
        
        // Artifact creation
        "artifact-model": anthropic("claude-sonnet-4-6"),
      },
    });