import { tool } from "ai";
import { z } from "zod";

export const ragSearch = tool({
    description: "Search the project documentation for information. This is the PRIMARY and ONLY source of truth for all project-related questions. Use this tool for ANY question about: project deliverables, timeline, milestones, team members, stakeholders, budget, resources, risks, or any project-specific information. If the answer is not found, return that the information is not in the documentation.",
    inputSchema: z.object({
        query: z.string().describe("The question to search for in the project documentation"),
    }),
  execute: async (input) => {
    try {
      console.log('🔍 RAG Search:', input.query);
      
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [
            {
              role: 'user',
              content: input.query,
            },
          ],
        }),
      });

      if (!response.ok) {
        console.error('RAG backend error:', response.status);
        return {
          error: 'Unable to search documentation at this time.',
        };
      }

      const data = await response.json();
      console.log('✅ RAG Result:', data.message);
      
      // Format response with citations
      let result = data.message;
      
      if (data.sources && data.sources.length > 0) {
        result += "\n\n**Sources:**\n";
        data.sources.forEach((source: any, index: number) => {
          const preview = source.content.substring(0, 100);
          result += `\n${index + 1}. "${preview}..." (Page: ${source.page})`;
        });
      }
      
      return {
        answer: result,
      };
    } catch (error) {
      console.error('RAG search failed:', error);
      return {
        error: 'Unable to search documentation at this time.',
      };
    }
  },
});