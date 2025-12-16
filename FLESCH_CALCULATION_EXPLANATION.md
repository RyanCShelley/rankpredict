# Flesch Reading Score Calculation and SERP Result Variability

## How Flesch Reading Score is Calculated

The Flesch Reading Ease Score is calculated using the standard formula:
```
Flesch Score = 206.835 - 1.015 × (words/sentences) - 84.6 × (syllables/words)
```

### Implementation Details

1. **Word Count**: Words are extracted from HTML content (using trafilatura or BeautifulSoup)
   - Only alphanumeric words are counted
   - Filtered to remove punctuation-only tokens

2. **Sentence Count**: Detected using regex pattern `[.!?]+`
   - If no sentences found, estimated as `word_count / 15`

3. **Syllable Calculation** (⚠️ **Key Source of Variability**):
   - Uses a heuristic vowel-based algorithm (not a dictionary lookup)
   - **Only samples the first 100 words** for performance
   - Calculates average syllables per word from this sample
   - If word count < 100, uses default of 1.5 syllables/word

4. **Final Score**: Clamped between 0-100

## Why You Get Different Results for the Same Query

### 1. **Caching Behavior**
- SERP results are cached in the `keyword_analyses` table
- When you generate an outline, it checks for cached analysis first
- **If cached data exists, it uses that instead of fetching fresh SERP data**
- Cached data doesn't expire automatically

### 2. **SERPAPI Result Variability**
When fresh data is fetched, results can differ because:
- **Google's rankings change over time** - different URLs may rank at different positions
- **Location-based differences** - results vary by geographic location
- **Time-of-day variations** - Google may serve different results at different times
- **Algorithm updates** - Google frequently updates its ranking algorithm

### 3. **Content Extraction Variability**
When fetching content from URLs:
- **Web pages change over time** - content updates on competitor sites
- **Dynamic content** - Some pages serve different content based on user agent, time, etc.
- **Extraction method** - Uses trafilatura first, falls back to BeautifulSoup if that fails
- **Network issues** - Some URLs may timeout or fail, resulting in default values (0 score)

### 4. **Sampling Bias in Syllable Calculation**
- Only **first 100 words** are analyzed for syllables
- Different word samples → different syllable averages → different Flesch scores
- This is the most significant source of calculation variability

### 5. **Median Calculation**
- Flesch scores are calculated for each of the top 10 results
- The **median** value is used for recommendations
- If the top 10 results change, the median changes

## Where Flesch Score is Used in Outline Generation

1. **SERP Analysis** (`backend/app/services/serp_service.py`)
   - Calculated for each competitor URL in top 10
   - Stored in `enriched_results`

2. **Median Calculation** (`backend/app/services/serp_service.py::calculate_serp_medians`)
   - Takes median of top 10 results
   - Falls back to 55.0 if median is < 10 (fix for buggy cached data)

3. **Content Strategy** (`backend/app/services/outline_service.py`)
   - Uses SERP median as target readability
   - Provides range: `target_flesch ± 5`

4. **Existing Content Analysis** (`backend/app/services/content_analyzer.py`)
   - Calculates Flesch for user's existing content
   - Compares against SERP median
   - Recommends SIMPLIFY, MAINTAIN, or ADD_DEPTH actions

## Recommendations to Reduce Variability

1. **Force Fresh Data**: Add option to force fresh SERP fetch (similar to `force_rescore` in strategy)
2. **Full Word Analysis**: Use all words instead of sampling first 100 (more accurate but slower)
3. **Caching Strategy**: Add cache expiration or versioning
4. **Logging**: Add detailed logging to track when cached vs fresh data is used
5. **Standardize Extraction**: Ensure consistent content extraction method

## Files Involved

- `backend/app/services/serp_service.py` - SERP fetching and enrichment
- `backend/app/services/content_analyzer.py` - Content analysis (existing content)
- `backend/app/services/outline_service.py` - Outline generation using Flesch scores
- `backend/app/api/outline.py` - Outline endpoint (uses cached or fresh data)
- `backend/app/api/strategy.py` - Keyword scoring (has force_rescore option)

