import { expect } from "chai";
import { GeminiTransformer } from "../src/transformer/gemini.transformer";
import { AnthropicTransformer } from "../src/transformer/anthropic.transformer";
import { DeepseekTransformer } from "../src/transformer/deepseek.transformer";
import { OpenAITransformer } from "../src/transformer/openai.transformer";

describe("Built-in transformers", () => {
  describe("GeminiTransformer", () => {
    const t = new GeminiTransformer();

    it("has correct name and endpoint", () => {
      expect(t.name).to.equal("gemini");
      expect(t.endPoint).to.equal("/v1beta/models/:modelAndAction");
    });

    it("transformRequestOut maps Gemini content to unified messages", () => {
      const request = {
        contents: [{ text: "hello" }],
        model: "gemini-2.5-flash",
        max_tokens: 100,
        temperature: 0.5,
        stream: false,
      };

      const out = t.transformRequestOut!(request, {});
      expect(out.messages).to.be.an("array").with.length(1);
      expect(out.messages[0].role).to.equal("user");
      expect(out.messages[0].content).to.equal("hello");
      expect(out.model).to.equal("gemini-2.5-flash");
      expect(out.max_tokens).to.equal(100);
      expect(out.temperature).to.equal(0.5);
      expect(out.stream).to.equal(false);
    });

    it("transformRequestOut handles string content array", () => {
      const request = {
        contents: ["hello", "world"],
        model: "gemini-pro",
      };

      const out = t.transformRequestOut!(request, {});
      expect(out.messages).to.have.length(2);
      expect(out.messages[0].content).to.equal("hello");
      expect(out.messages[1].content).to.equal("world");
    });
  });

  describe("AnthropicTransformer", () => {
    const t = new AnthropicTransformer();

    it("has correct name and endpoint", () => {
      expect(t.name).to.equal("Anthropic");
      expect(t.endPoint).to.equal("/v1/messages");
    });

    it("transformRequestOut maps Anthropic messages to unified format", async () => {
      const request = {
        messages: [
          { role: "user", content: "hello" },
          { role: "assistant", content: "hi there" },
        ],
        model: "claude-sonnet-4-6",
        max_tokens: 200,
        temperature: 0.7,
        stream: false,
        system: "system prompt",
      };

      const out = await t.transformRequestOut!(request, {});
      expect(out.messages).to.be.an("array");
      expect(out.messages[0].role).to.equal("system");
      expect(out.messages[0].content).to.equal("system prompt");
      expect(out.messages[1].role).to.equal("user");
      expect(out.messages[1].content).to.equal("hello");
      expect(out.model).to.equal("claude-sonnet-4-6");
      expect(out.max_tokens).to.equal(200);
      expect(out.temperature).to.equal(0.7);
    });

    it("transformRequestOut handles system as array", async () => {
      const request = {
        messages: [{ role: "user", content: "hi" }],
        model: "claude-3-opus",
        system: [{ type: "text", text: "sys1" }, { type: "text", text: "sys2" }],
      };

      const out = await t.transformRequestOut!(request, {});
      expect(out.messages[0].role).to.equal("system");
      expect(Array.isArray(out.messages[0].content)).to.be.true;
    });
  });

  describe("DeepseekTransformer", () => {
    const t = new DeepseekTransformer();

    it("has correct name", () => {
      expect(t.name).to.equal("deepseek");
    });

    it("transformRequestIn caps max_tokens at 8192", async () => {
      const request = {
        messages: [{ role: "user", content: "solve" }],
        model: "deepseek-chat",
        max_tokens: 10000,
      };

      const out = await t.transformRequestIn!(request);
      expect(out.max_tokens).to.equal(8192);
    });

    it("transformRequestIn passes through when below limit", async () => {
      const request = {
        messages: [{ role: "user", content: "hi" }],
        model: "deepseek-chat",
        max_tokens: 100,
      };

      const out = await t.transformRequestIn!(request);
      expect(out.max_tokens).to.equal(100);
    });
  });

  describe("OpenAITransformer", () => {
    const t = new OpenAITransformer();

    it("has correct name and endpoint", () => {
      expect(t.name).to.equal("OpenAI");
      expect(t.endPoint).to.equal("/v1/chat/completions");
    });
  });
});
