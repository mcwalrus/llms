import { expect } from "chai";
import sinon from "sinon";
import { ConfigService } from "@/services/config";

describe("ConfigService", () => {
  it("merges initialConfig and provides get/has/set/getAll", () => {
    const config = new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
      initialConfig: { foo: "bar", num: 42 },
    });
    expect(config.has("foo")).to.be.true;
    expect(config.get("foo")).to.equal("bar");
    expect(config.get("num")).to.equal(42);
    expect(config.get("missing")).to.be.undefined;
    expect(config.get("missing", "fallback")).to.equal("fallback");

    config.set("baz", 99);
    expect(config.get("baz")).to.equal(99);
    expect(config.getAll()).to.deep.include({ foo: "bar", num: 42, baz: 99 });
  });

  it("has returns false for absent keys", () => {
    const config = new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
    });
    expect(config.has("nope")).to.be.false;
  });

  it("getHttpsProxy resolves in order of preference", () => {
    const config = new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
      initialConfig: {
        HTTPS_PROXY: "http://first",
        https_proxy: "http://second",
      },
    });
    expect(config.getHttpsProxy()).to.equal("http://first");
  });

  it("getHttpsProxy returns undefined when absent", () => {
    const config = new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
    });
    expect(config.getHttpsProxy()).to.be.undefined;
  });

  it("getConfigSummary lists active sources", () => {
    const config = new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
      initialConfig: { foo: 1 },
    });
    expect(config.getConfigSummary()).to.include("Initial Config");
  });

  it("reload resets and rebuilds config", () => {
    const config = new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
      initialConfig: { port: 3000 },
    });
    config.set("port", 9999);
    expect(config.get("port")).to.equal(9999);

    config.reload();
    expect(config.get("port")).to.equal(3000);
  });

  it("side-effects: sets LOG_FILE and LOG env vars", () => {
    delete process.env.LOG_FILE;
    delete process.env.LOG;

    new ConfigService({
      useJsonFile: false,
      useEnvFile: false,
      initialConfig: { LOG_FILE: "/tmp/out.log", LOG: "debug" },
    });
    expect(process.env.LOG_FILE).to.equal("/tmp/out.log");
    expect(process.env.LOG).to.equal("debug");
    delete process.env.LOG_FILE;
    delete process.env.LOG;
  });
});
