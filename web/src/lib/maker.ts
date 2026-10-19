// The maker's name, quote and links. Career details live on the linked portfolio, not here
// (owner, 2026-10-19). The name has an Urdu form; the quote stays in English.
export const MAKER = {
  name: { en: "Ahmad Uzzam Masood", ur: "احمد عزام مسعود" } as Record<string, string>,
  quote: "I design data systems that stay fast, governed, and cost-efficient at scale.",
  links: {
    portfolio: "https://azzammasood.github.io/",
    github: "https://github.com/azzammasood",
    linkedin: "https://www.linkedin.com/in/azzammasood/",
    code: "https://github.com/azzammasood/roshni-pipeline",
  },
} as const;

export const makerName = (locale: string) => MAKER.name[locale] ?? MAKER.name.en;
