// The maker's details, from his own public pages (portfolio azzammasood.github.io/about and the
// GitHub profile, read 2026-10-18; owner asked for them on the site). Proper nouns stay Latin in
// both languages; the words around them live in the dictionaries.
export const MAKER = {
  name: { en: "Ahmad Uzzam Masood", ur: "احمد عزام مسعود" } as Record<string, string>,
  clouds: "AWS · Azure · GCP",
  company: "Nayatel",
  university: "COMSATS University Islamabad",
  platform: "Spotify",
  quote: "I design data systems that stay fast, governed, and cost-efficient at scale.",
  skills: ["Python", "SQL", "PySpark", "dbt", "Airflow", "Kafka", "Apache Iceberg", "AWS", "Redshift", "Terraform", "Docker", "Kubernetes"],
  links: {
    portfolio: "https://azzammasood.github.io/",
    github: "https://github.com/azzammasood",
    linkedin: "https://www.linkedin.com/in/azzammasood/",
    code: "https://github.com/azzammasood/roshni-pipeline",
  },
} as const;

export const makerName = (locale: string) => MAKER.name[locale] ?? MAKER.name.en;
