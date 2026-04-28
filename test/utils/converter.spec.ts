import { expect } from "chai";
import {
  convertToolsToOpenAI,
  convertToolsToAnthropic,
  convertToolsFromOpenAI,
  convertToolsFromAnthropic,
  convertToOpenAI,
  convertFromOpenAI,
  convertFromAnthropic,
  convertRequest,
} from "@/utils/converter";
import {
  UnifiedTool,
  UnifiedChatRequest,
  OpenAIChatRequest,
  AnthropicChatRequest,
} from "@/types/llm";

const sampleTool: UnifiedTool = {
  type: "function",
  function: {
    name: "get_weather",
    description: "Fetches weather",
    parameters: {
      type: "object",
      properties: { city: { type: "string" } },
      required: ["city"],
    },
  },
};

const sampleOpenAITool = {
  type: "function" as const,
  function: {
    name: "get_weather",
    description: "Fetches weather",
    parameters: { type: "object", properties: { city: { type: "string" } } },
  },
};

const sampleAnthropicTool = {
  name: "get_weather",
  description: "Fetches weather",
  input_schema: { type: "object", properties: { city: { type: "string" } } },
};

describe("converter — tool conversions", () => {
  it("convertToolsToOpenAI maps UnifiedTool[] → ChatCompletionTool[]", () => {
    const result = convertToolsToOpenAI([sampleTool]);
    expect(result).to.have.length(1);
    expect(result[0].type).to.equal("function");
    expect(result[0].function.name).to.equal("get_weather");
  });

  it("convertToolsToAnthropic maps UnifiedTool[] → AnthropicTool[]", () => {
    const result = convertToolsToAnthropic([sampleTool]);
    expect(result).to.have.length(1);
    expect(result[0].name).to.equal("get_weather");
    expect(result[0].input_schema).to.deep.equal(
      sampleTool.function.parameters
    );
  });

  it("convertToolsFromOpenAI round-trips with convertToolsToOpenAI", () => {
    const openAI = [sampleOpenAITool];
    const unified = convertToolsFromOpenAI(openAI as any);
    expect(unified).to.have.length(1);
    expect(unified[0].function.name).to.equal("get_weather");
  });

  it("convertToolsFromAnthropic round-trips with convertToolsToAnthropic", () => {
    const anthropic = [sampleAnthropicTool];
    const unified = convertToolsFromAnthropic(anthropic as any);
    expect(unified).to.have.length(1);
    expect(unified[0].function.name).to.equal("get_weather");
  });
});

describe("converter — message conversions", () => {
  it("convertToOpenAI builds OpenAI request from UnifiedChatRequest", () => {
    const request: UnifiedChatRequest = {
      messages: [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi there" },
      ],
      model: "gpt-4",
      max_tokens: 256,
      temperature: 0.7,
      stream: false,
      tools: [sampleTool],
      tool_choice: "auto",
    };
    const result = convertToOpenAI(request);
    expect(result.model).to.equal("gpt-4");
    expect(result.messages).to.have.length(2);
    expect(result.tools).to.have.length(1);
    expect(result.tool_choice).to.equal("auto");
  });

  it("convertFromOpenAI handles simple messages", () => {
    const request: OpenAIChatRequest = {
      messages: [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi there" },
      ],
      model: "gpt-4",
    };
    const result = convertFromOpenAI(request);
    expect(result.messages).to.have.length(2);
    expect(result.messages[0].role).to.equal("user");
    expect(result.messages[1].role).to.equal("assistant");
  });

  it("convertFromAnthropic merges system message into UnifiedChatRequest", () => {
    const request: AnthropicChatRequest = {
      system: "You are a helpful assistant.",
      messages: [{ role: "user", content: "Hello" }],
      model: "claude-3",
    };
    const result = convertFromAnthropic(request);
    expect(result.messages[0].role).to.equal("system");
    expect(result.messages[0].content).to.equal("You are a helpful assistant.");
    expect(result.messages[1].role).to.equal("user");
  });

  it("convertRequest round-trips OpenAI → OpenAI (noop)", () => {
    const openAI: OpenAIChatRequest = {
      messages: [{ role: "user", content: "Hello" }],
      model: "gpt-4",
      tools: [sampleOpenAITool as any],
      tool_choice: "auto",
    };
    const result = convertRequest(openAI, {
      sourceProvider: "openai",
      targetProvider: "openai",
    });
    expect(result.model).to.equal("gpt-4");
    expect((result as any).messages[0].content).to.equal("Hello");
  });
});

describe("converter — tool_choice handling", () => {
  it("convertToOpenAI maps named tool_choice to function object", () => {
    const request: UnifiedChatRequest = {
      messages: [],
      model: "gpt-4",
      tool_choice: "get_weather",
      tools: [sampleTool],
    };
    const result = convertToOpenAI(request);
    expect(result.tool_choice).to.deep.equal({
      type: "function",
      function: { name: "get_weather" },
    });
  });

  it("convertFromOpenAI preserves string tool_choice", () => {
    const request: OpenAIChatRequest = {
      messages: [],
      model: "gpt-4",
      tool_choice: "auto",
      tools: [sampleOpenAITool as any],
    };
    const result = convertFromOpenAI(request);
    expect(result.tool_choice).to.equal("auto");
  });

  it("convertFromOpenAI maps function tool_choice back to string", () => {
    const request: OpenAIChatRequest = {
      messages: [],
      model: "gpt-4",
      tool_choice: {
        type: "function",
        function: { name: "get_weather" } as any,
      },
      tools: [sampleOpenAITool as any],
    };
    const result = convertFromOpenAI(request);
    expect(result.tool_choice).to.equal("get_weather");
  });
});
