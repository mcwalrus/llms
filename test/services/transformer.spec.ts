import { expect } from "chai";
import { TransformerService } from "@/services/transformer";
import { ConfigService } from "@/services/config";

describe("TransformerService", () => {
  const logger = {
    info: () => {},
    error: () => {},
  };

  it("registers a transformer and retrieves it", () => {
    const config = new ConfigService({ useJsonFile: false, useEnvFile: false });
    const svc = new TransformerService(config as any, logger);
    const t = { name: "t1", endPoint: "/test" };
    svc.registerTransformer("t1", t);
    expect(svc.hasTransformer("t1")).to.be.true;
    expect(svc.getTransformer("t1")).to.equal(t);
    expect(svc.getTransformer("missing")).to.be.undefined;
  });

  it("removes a transformer", () => {
    const config = new ConfigService({ useJsonFile: false, useEnvFile: false });
    const svc = new TransformerService(config as any, logger);
    svc.registerTransformer("t1", { name: "t1" });
    expect(svc.removeTransformer("t1")).to.be.true;
    expect(svc.hasTransformer("t1")).to.be.false;
  });

  it("lists transformers with/without endpoints", () => {
    const config = new ConfigService({ useJsonFile: false, useEnvFile: false });
    const svc = new TransformerService(config as any, logger);
    svc.registerTransformer("with", { name: "with", endPoint: "/ep" });
    svc.registerTransformer("without", { name: "without" });

    const withEp = svc.getTransformersWithEndpoint();
    const withoutEp = svc.getTransformersWithoutEndpoint();

    expect(withEp.map((x) => x.name)).to.deep.equal(["with"]);
    expect(withoutEp.map((x) => x.name)).to.deep.equal(["without"]);
  });

  it("getAllTransformers returns a copy", () => {
    const config = new ConfigService({ useJsonFile: false, useEnvFile: false });
    const svc = new TransformerService(config as any, logger);
    svc.registerTransformer("t1", { name: "t1" });
    expect(svc.getAllTransformers().size).to.equal(1);
  });

  it("initializes default transformers without error", async () => {
    const config = new ConfigService({ useJsonFile: false, useEnvFile: false });
    const svc = new TransformerService(config as any, logger);
    await svc.initialize();
    expect(svc.getAllTransformers().size).to.be.greaterThan(0);
    expect(svc.hasTransformer("maxtoken")).to.be.true;
    expect(svc.hasTransformer("sampling")).to.be.true;
  });
});
