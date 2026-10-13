import { describe, expect, it } from "vitest";
import { censusName, circleName, ibcName } from "./names";

describe("display names", () => {
  it("names IESCO circles", () => {
    expect(circleName("ajk")).toBe("AJK");
    expect(circleName("rawalpindi")).toBe("Rawalpindi");
    expect(circleName(null)).toBeNull();
  });
  it("re-cases census names but keeps acronyms", () => {
    expect(censusName("NORTH NAZIMABAD SUB-DIVISION")).toBe("North Nazimabad Sub-division");
    expect(censusName("SITE SUB-DIVISION")).toBe("SITE Sub-division");
    expect(censusName("Already Mixed")).toBe("Already Mixed");
  });
  it("drops the IBC prefix", () => {
    expect(ibcName("IBC - Orangi - I")).toBe("Orangi - I");
    expect(ibcName("Clifton")).toBe("Clifton");
  });
});
