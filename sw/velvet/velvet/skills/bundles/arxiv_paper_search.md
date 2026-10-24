---
name: arxiv_paper_search
description: Search ArXiv for scientific literature, preprints, and research papers; retrieve abstracts and summaries.
category: Research
autonomy_required: LEVEL_1
parameters: query:string:Search keywords or ArXiv ID, max_results:int:Maximum number of papers to retrieve (default 5), sort_by:string:Sort order (relevance, lastUpdatedDate, submittedDate)
tags: [science, research, arxiv, papers, literature, academic, preprints]
---

# ArXiv Scientific Literature Search

This skill queries the ArXiv API for preprints and academic research papers across computer science, physics, mathematics, biology, and quantitative finance.

## API Query Protocol

1. **Construct API Request**:
   - Base endpoint: `http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_results}&sortBy={sort_by}`
   - If an exact ArXiv ID is provided (e.g., `2301.00001`), query by ID: `id_list={query}`.

2. **Response Parsing**:
   - Parse Atom XML response to extract:
     - Title
     - Authors (comma-separated list)
     - Published & Updated dates
     - ArXiv ID & PDF Link
     - Abstract / Summary

3. **Synthesis & Summarization**:
   - Format each retrieved paper into a structured research note.
   - Highlight key contributions, methodology, and relevance to the user's inquiry.

## Output Formatting

Return a clean markdown report containing:
- A summary overview of the search results
- For each paper:
  - **Title** (with clickable link to PDF)
  - **Authors** & **Publication Date**
  - **Abstract Summary** (concise 3-4 bullet breakdown of key findings)
  - **ArXiv Reference ID**
