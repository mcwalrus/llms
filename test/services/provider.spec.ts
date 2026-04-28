import { expect } from "chai";
import { ProviderService } from "@/services/provider";
import { ConfigService } from "@/services/config";
import { TransformerService } from "@/services/transformer";

describe("ProviderService", () => {
  const logger = { info: () => {}, error: () => {} };

  function makeServices() {
    const config = new ConfigService({ useJsonFile: false, useEnvFile: false });
    const transformerService = new TransformerService(config as any, logger);
    const providerService = new ProviderService(
      config as any,
      transformerService,
      logger
    );
    return { config, transformerService, providerService };
  }

  it("registers a provider and resolves its model route", () => {
    const { providerService } = makeServices();
    const provider = providerService.registerProvider({
      name: "openai",
      baseUrl: "https://api.openai.com",
      apiKey: "sk-test",
      models: ["gpt-4", "gpt-3.5"],
    });
    expect(provider.name).to.equal("openai");
    expect(providerService.getProvider("openai")).to.equal(provider);

    const route = providerService.resolveModelRoute("openai,gpt-4");
    expect(route).to.not.be.null;
    expect(route!.provider.name).to.equal("openai");
    expect(route!.targetModel).to.equal("gpt-4");

    const bare = providerService.resolveModelRoute("gpt-3.5");
    expect(bare).to.not.be.null;
    expect(bare!.targetModel).to.equal("gpt-3.5");
  });

  it("getProviders returns all registered providers", () => {
    const { providerService } = makeServices();
    providerService.registerProvider({
      name: "a",
      baseUrl: "http://a",
      apiKey: "k",
      models: ["m1"],
    });
    providerService.registerProvider({
      name: "b",
      baseUrl: "http://b",
      apiKey: "k",
      models: ["m2"],
    });
    expect(providerService.getProviders()).to.have.length(2);
  });

  it("deleteProvider removes provider and model routes", () => {
    const { providerService } = makeServices();
    providerService.registerProvider({
      name: "x",
      baseUrl: "http://x",
      apiKey: "k",
      models: ["model-a"],
    });
    expect(providerService.deleteProvider("x")).to.be.true;
    expect(providerService.getProvider("x")).to.be.undefined;
    expect(providerService.resolveModelRoute("x,model-a")).to.be.null;
  });

  it("deleteProvider returns false for unknown id", () => {
    const { providerService } = makeServices();
    expect(providerService.deleteProvider("ghost")).to.be.false;
  });

  it("updateProvider mutates provider and rebuilds routes", () => {
    const { providerService } = makeServices();
    providerService.registerProvider({
      name: "p",
      baseUrl: "http://p",
      apiKey: "k",
      models: ["m1"],
    });
    const updated = providerService.updateProvider("p", {
      models: ["m2"],
    });
    expect(updated).to.not.be.null;
    expect(updated!.models).to.deep.equal(["m2"]);
    expect(providerService.resolveModelRoute("p,m2")).to.not.be.null;
    expect(providerService.resolveModelRoute("p,m1")).to.be.null;
    expect(providerService.resolveModelRoute("m1")).to.be.null;
    expect(providerService.resolveModelRoute("m2")).to.not.be.null;
  });

  it("toggleProvider returns false for unknown", () => {
    const { providerService } = makeServices();
    expect(providerService.toggleProvider("ghost", true)).to.be.false;
  });

  it("resolveModelRoute returns null for unknown model", () => {
    const { providerService } = makeServices();
    expect(providerService.resolveModelRoute("none")).to.be.null;
  });

  it("getAvailableModelNames lists all models", () => {
    const { providerService } = makeServices();
    providerService.registerProvider({
      name: "p",
      baseUrl: "http://p",
      apiKey: "k",
      models: ["m1"],
    });
    const names = providerService.getAvailableModelNames();
    expect(names).to.include("m1");
    expect(names).to.include("p,m1");
  });

  it("getModelRoutes returns route entries", () => {
    const { providerService } = makeServices();
    providerService.registerProvider({
      name: "p",
      baseUrl: "http://p",
      apiKey: "k",
      models: ["m1"],
    });
    expect(providerService.getModelRoutes()).to.have.length(2); // m1 and p,m1
  });

  it("getAvailableModels returns OpenAI-compatible list", async () => {
    const { providerService } = makeServices();
    providerService.registerProvider({
      name: "p",
      baseUrl: "http://p",
      apiKey: "k",
      models: ["m1"],
    });
    const list = await providerService.getAvailableModels();
    expect(list.object).to.equal("list");
    expect(list.data).to.have.length(2);
    expect(list.data[0].id).to.equal("m1");
  });
});
