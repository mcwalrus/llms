import { expect } from "chai";
import sinon from "sinon";
import { parseToolArguments } from "@/utils/toolArgumentsParser";

describe("parseToolArguments", () => {
  let logger: { debug: sinon.SinonStub; error: sinon.SinonStub };

  beforeEach(() => {
    logger = {
      debug: sinon.stub(),
      error: sinon.stub(),
    };
  });

  afterEach(() => {
    sinon.restore();
  });

  it("returns '\\{\\}' for empty input", () => {
    expect(parseToolArguments("")).to.equal("{}");
    expect(parseToolArguments("  ")).to.equal("{}");
    expect(parseToolArguments("{}")).to.equal("{}");
  });

  it("returns valid JSON unchanged and logs debug", () => {
    const json = '{"name":"test","value":42}';
    const result = parseToolArguments(json, logger as any);
    expect(result).to.equal(json);
    expect(logger.debug.calledOnce).to.be.true;
  });

  it("parses relaxed JSON5 and returns normalized JSON", () => {
    const json5 = "{name: 'test', value: 42,}";
    const result = parseToolArguments(json5, logger as any);
    expect(result).to.equal('{"name":"test","value":42}');
    expect(logger.debug.calledOnce).to.be.true;
  });

  it("repairs malformed JSON and returns debug log", () => {
    const broken = '{"name": "test", "value": 42';
    const result = parseToolArguments(broken, logger as any);
    expect(JSON.parse(result)).to.deep.equal({ name: "test", value: 42 });
    expect(logger.debug.calledOnce).to.be.true;
  });

  it("logs errors and returns '{}' when all parsers fail", () => {
    const garbage = "not json at all {{{";
    const result = parseToolArguments(garbage, logger as any);
    expect(result).to.equal("{}");
    expect(logger.error.calledOnce).to.be.true;
    expect(logger.debug.calledOnce).to.be.true;
  });

  it("works without a logger (no crash)", () => {
    const result = parseToolArguments('{"a":1}');
    expect(result).to.equal('{"a":1}');
  });
});
