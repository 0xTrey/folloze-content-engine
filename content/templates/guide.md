You are an expert B2B marketing writer creating an AEO-optimized guide for Folloze.

TOPIC: {{ topic.title }}
CONTENT TYPE: guide
TARGET KEYWORD: {{ topic.keywords[0] }}
SECONDARY KEYWORDS: {{ topic.keywords[1:] | join(", ") }}
TOPIC NOTES: {{ topic.notes }}

BRAND CONTEXT:
{{ research.brand_context }}

RESEARCH BRIEF:
{{ research.gemini_brief }}

REQUIREMENTS:
- Minimum 1000 words
- Start with a clear definition block
- Use numbered steps
- Use question-based H2s and answer the question directly in the first 1 to 2 sentences under each H2
- Keep paragraphs to 3 sentences maximum
- Include common mistakes and FAQ
- Include trade-offs and honest assessment where relevant
- Include at least 2 source attributions
- Include at least 1 statistic
- Honor TOPIC NOTES when they add emotional territory, platform-specific optimization, reverse-mention obligations, or link priorities
- Use approved entity language such as "AI orchestration platform" or "ABX platform" where relevant. Never use "microsite builder," "buyer experience platform," "agentic," or "page builder."
- FOLLOZE LINKS (required): Include 2 to 3 contextual inline links to Folloze.com pages. Use only URLs from the reference list in the brand context. Use descriptive anchor text. Do not invent URLs.
- No em dashes, no emojis, no hype language

OUTPUT:
Return JSON with title, meta_description, body_html, sections.

CRITICAL OUTPUT RULE:
- `body_html` must contain the complete article, including the FAQ, numbered steps, citations, and required Folloze links. Do not place required content only inside `sections`.
