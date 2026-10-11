import { describe, expect, it } from "vitest";
import { feederSlug, slugIndex } from "./slug";

describe("feederSlug", () => {
  it("lowercases and replaces separators", () => {
    expect(feederSlug("iesco:ajk:048101")).toBe("iesco-ajk-048101");
    expect(feederSlug("ke:36BRMU")).toBe("ke-36brmu");
  });
  it("rejects collisions", () => {
    expect(() => slugIndex([{ feeder_id: "ke:33E" }, { feeder_id: "ke:33e" }])).toThrow(/collision/);
  });
});
