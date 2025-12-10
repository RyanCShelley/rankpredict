import { useState, useEffect } from 'react';
import { outlineAPI } from '../services/api';

const OutlineBuilder = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [keywords, setKeywords] = useState([]);
  const [selectedKeywordId, setSelectedKeywordId] = useState(null);
  const [contentType, setContentType] = useState('new');
  const [existingUrl, setExistingUrl] = useState('');
  const [targetIntent, setTargetIntent] = useState(''); // '' means auto-detect from SERP
  const [outline, setOutline] = useState(null);
  const [improvementPlan, setImprovementPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // Saved briefs state
  const [savedBriefs, setSavedBriefs] = useState([]);
  const [loadingBriefs, setLoadingBriefs] = useState(false);
  const [showSavedBriefs, setShowSavedBriefs] = useState(false);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Load keywords and briefs when project changes
  useEffect(() => {
    if (selectedProjectId) {
      loadKeywordsByProject(selectedProjectId);
      loadSavedBriefs(selectedProjectId);
    }
  }, [selectedProjectId]);

  const loadProjects = async () => {
    try {
      const data = await outlineAPI.getProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProjectId) {
        setSelectedProjectId(data[0].id);
      }
    } catch (err) {
      console.error('Error loading projects:', err);
    }
  };

  const loadKeywordsByProject = async (projectId) => {
    try {
      const data = await outlineAPI.getKeywordsByProject(projectId);
      setKeywords(data);
      setSelectedKeywordId(null); // Reset keyword selection
      if (data.length > 0) {
        setSelectedKeywordId(data[0].id);
      }
    } catch (err) {
      console.error('Error loading keywords:', err);
    }
  };

  const loadSavedBriefs = async (projectId) => {
    setLoadingBriefs(true);
    try {
      const data = await outlineAPI.getSavedBriefs(projectId);
      setSavedBriefs(data);
    } catch (err) {
      console.error('Error loading saved briefs:', err);
    } finally {
      setLoadingBriefs(false);
    }
  };

  const handleViewSavedBrief = async (briefId) => {
    setLoading(true);
    setError('');
    try {
      const data = await outlineAPI.getSavedBrief(briefId);
      setOutline(data);
      setShowSavedBriefs(false);
    } catch (err) {
      setError('Error loading brief: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBrief = async (briefId) => {
    if (!window.confirm('Are you sure you want to delete this brief?')) return;
    try {
      await outlineAPI.deleteBrief(briefId);
      loadSavedBriefs(selectedProjectId);
    } catch (err) {
      setError('Error deleting brief: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDownloadPdf = async (briefId, keyword) => {
    try {
      const blob = await outlineAPI.downloadBriefPdf(briefId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `brief_${keyword.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError('Error downloading PDF: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleGenerateOutline = async () => {
    if (!selectedKeywordId) {
      setError('Please select a keyword');
      return;
    }

    if (contentType === 'existing' && !existingUrl.trim()) {
      setError('Please enter the URL of existing content');
      return;
    }

    setLoading(true);
    setError('');
    setOutline(null);
    setImprovementPlan(null);

    try {
      const data = await outlineAPI.generateOutline(
        selectedKeywordId,
        contentType,
        contentType === 'existing' ? existingUrl : null,
        targetIntent || null // null means auto-detect from SERP
      );
      setOutline(data);

      // Refresh saved briefs list
      if (selectedProjectId) {
        loadSavedBriefs(selectedProjectId);
      }

      // If existing content, also fetch improvement plan
      if (contentType === 'existing' && existingUrl) {
        try {
          const plan = await outlineAPI.getImprovementPlan(selectedKeywordId, existingUrl);
          setImprovementPlan(plan);
        } catch (err) {
          console.error('Error fetching improvement plan:', err);
        }
      }
    } catch (err) {
      console.error('Outline generation error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Network Error';
      setError(`Error generating outline: ${errorMessage}`);

      if (err.message === 'Network Error' || err.code === 'ECONNREFUSED') {
        setError('Cannot connect to server. Please ensure the backend is running on port 8000.');
      }
    } finally {
      setLoading(false);
    }
  };

  const selectedKeyword = keywords.find(k => k.id === selectedKeywordId);

  // Helper to get feature badge color
  const getFeatureBadgeColor = (feature) => {
    const colors = {
      'people_also_ask': 'bg-purple-100 text-purple-800',
      'related_searches': 'bg-blue-100 text-blue-800',
      'featured_snippet': 'bg-green-100 text-green-800',
      'knowledge_panel': 'bg-yellow-100 text-yellow-800',
      'ads': 'bg-red-100 text-red-800',
      'local_pack': 'bg-orange-100 text-orange-800',
      'video_results': 'bg-pink-100 text-pink-800',
      'image_results': 'bg-cyan-100 text-cyan-800',
      'news_results': 'bg-indigo-100 text-indigo-800',
      'shopping_results': 'bg-emerald-100 text-emerald-800'
    };
    return colors[feature] || 'bg-gray-100 text-gray-800';
  };

  const formatFeatureName = (feature) => {
    return feature.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">Content Brief Builder</h1>
      <p className="text-gray-600 mb-8">
        Generate AI-powered content briefs based on SERP analysis, PAA questions, and competitor research
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Project and Keyword Selection */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Select Project & Keyword</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Project
              </label>
              <select
                value={selectedProjectId || ''}
                onChange={(e) => setSelectedProjectId(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">Select a project...</option>
                {projects.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.selected_count}/{p.keyword_count} approved)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Keyword (sorted by rankability)
              </label>
              <select
                value={selectedKeywordId || ''}
                onChange={(e) => setSelectedKeywordId(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                disabled={!selectedProjectId}
              >
                <option value="">Select a keyword...</option>
                {keywords.map(k => (
                  <option key={k.id} value={k.id}>
                    {k.keyword} ({(k.rankability_score * 100).toFixed(1)}% - {k.opportunity_tier})
                  </option>
                ))}
              </select>
              {selectedProjectId && keywords.length === 0 && (
                <p className="text-sm text-orange-600 mt-1">
                  No approved keywords in this project. Approve keywords in Strategy Dashboard first.
                </p>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Content Type
            </label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="new"
                  checked={contentType === 'new'}
                  onChange={(e) => setContentType(e.target.value)}
                  className="mr-2"
                />
                New Content
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="existing"
                  checked={contentType === 'existing'}
                  onChange={(e) => setContentType(e.target.value)}
                  className="mr-2"
                />
                Existing Content
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Target Page Intent
            </label>
            <select
              value={targetIntent}
              onChange={(e) => setTargetIntent(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">Auto-detect from SERP</option>
              <option value="informational">Informational - Educational content, how-to guides, explanations</option>
              <option value="commercial">Commercial - Comparisons, reviews, "best of" lists, buying guides</option>
              <option value="transactional">Transactional - Service pages, pricing, CTAs, conversion-focused</option>
              <option value="navigational">Navigational - Brand-focused, direct answers, contact info</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Override SERP-detected intent to create content optimized for a specific page type
            </p>
          </div>

          {contentType === 'existing' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Existing Content URL
              </label>
              <input
                type="url"
                value={existingUrl}
                onChange={(e) => setExistingUrl(e.target.value)}
                placeholder="https://example.com/page"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleGenerateOutline}
              disabled={loading || !selectedKeywordId}
              className="px-6 py-3 bg-[#223540] text-white rounded-md hover:bg-[#00a99d] disabled:opacity-50"
            >
              {loading ? 'Generating Brief...' : 'Generate Content Brief'}
            </button>
            {savedBriefs.length > 0 && (
              <button
                onClick={() => setShowSavedBriefs(!showSavedBriefs)}
                className="px-4 py-3 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                {showSavedBriefs ? 'Hide' : 'Show'} Saved Briefs ({savedBriefs.length})
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Saved Briefs Section */}
      {showSavedBriefs && savedBriefs.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Saved Briefs</h2>
          {loadingBriefs ? (
            <p className="text-gray-500">Loading briefs...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keyword</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {savedBriefs.map(brief => (
                    <tr key={brief.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{brief.keyword}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {brief.content_type === 'existing' ? 'Existing' : 'New'}
                        {brief.target_intent && ` (${brief.target_intent})`}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {brief.created_at ? new Date(brief.created_at).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleViewSavedBrief(brief.id)}
                            className="text-blue-600 hover:text-blue-800"
                            title="View brief"
                          >
                            View
                          </button>
                          <button
                            onClick={() => handleDownloadPdf(brief.id, brief.keyword)}
                            className="text-green-600 hover:text-green-800"
                            title="Download PDF"
                          >
                            PDF
                          </button>
                          <button
                            onClick={() => handleDeleteBrief(brief.id)}
                            className="text-red-600 hover:text-red-800"
                            title="Delete brief"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Improvement Plan (Existing Content) */}
      {improvementPlan && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Improvement Plan</h2>
          <div className="space-y-4">
            <div>
              <h3 className="font-medium mb-2">Gap Analysis</h3>
              <div className="space-y-2">
                {Object.entries(improvementPlan.gap_analysis || {}).map(([metric, data]) => (
                  <div key={metric} className="border-l-4 border-blue-500 pl-4">
                    <div className="font-medium">{metric}</div>
                    <div className="text-sm text-gray-600">
                      Current: {data.current?.toFixed(0) || 0} → Target: {data.target?.toFixed(0) || 0}
                      {data.gap_percentage && (
                        <span className={`ml-2 ${data.gap_percentage < 0 ? 'text-red-600' : 'text-green-600'}`}>
                          ({data.gap_percentage > 0 ? '+' : ''}{data.gap_percentage.toFixed(0)}%)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-medium mb-2">Priority Actions</h3>
              <div className="space-y-2">
                {improvementPlan.priority_actions?.map((action, idx) => (
                  <div key={idx} className="border-l-4 border-yellow-500 pl-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="font-medium">{action.metric}</div>
                        <div className="text-sm text-gray-600">{action.issue}</div>
                        <div className="text-sm text-blue-600 mt-1">{action.action}</div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs ${
                        action.priority === 'High' ? 'bg-red-100 text-red-800' :
                        action.priority === 'Medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {action.priority}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Content Brief Display */}
      {outline && (
        <div className="space-y-6">
          {/* Header Section */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="mb-4">
              {outline.optimization_mode && (
                <div className="mb-3 px-3 py-2 bg-orange-100 border border-orange-300 rounded-lg">
                  <p className="text-sm font-medium text-orange-800">
                    Optimization Brief for Existing Content
                  </p>
                  {outline.existing_url && (
                    <a href={outline.existing_url} target="_blank" rel="noopener noreferrer" className="text-xs text-orange-600 hover:underline break-all">
                      {outline.existing_url}
                    </a>
                  )}
                </div>
              )}
              <h2 className="text-2xl font-bold text-[#223540]">{outline.keyword}</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                  {outline.optimization_mode ? 'Optimization' : (outline.intent_analysis?.intent_type || 'Informational')}
                </span>
                <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded text-sm">
                  {outline.structure_type || 'Article'}
                </span>
              </div>
            </div>

            {/* Title & Meta Recommendation */}
            {outline.title_recommendation && (
              <div className="mt-4 p-4 bg-green-50 rounded-lg border border-green-200">
                <h3 className="font-semibold text-green-800 mb-2">Recommended Title (H1)</h3>
                <p className="text-lg font-medium">{outline.title_recommendation}</p>
                {outline.meta_description && (
                  <>
                    <h4 className="font-semibold text-green-800 mt-3 mb-1">Meta Description</h4>
                    <p className="text-sm text-gray-700">{outline.meta_description}</p>
                  </>
                )}
              </div>
            )}
          </div>

          {/* SERP Features Present */}
          {outline.serp_features && outline.serp_features.serp_features_present?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">SERP Features Present</h3>
              <div className="flex flex-wrap gap-2 mb-4">
                {outline.serp_features.serp_features_present.map((feature, idx) => (
                  <span key={idx} className={`px-3 py-1 rounded text-sm font-medium ${getFeatureBadgeColor(feature)}`}>
                    {formatFeatureName(feature)}
                  </span>
                ))}
              </div>

              {/* Featured Snippet */}
              {outline.serp_features.featured_snippet && (
                <div className="mt-4 p-4 bg-green-50 rounded-lg border border-green-200">
                  <h4 className="font-semibold text-green-800 mb-2">Featured Snippet Opportunity</h4>
                  <p className="text-sm font-medium">Type: {outline.serp_features.featured_snippet.type}</p>
                  {outline.serp_features.featured_snippet.snippet && (
                    <p className="text-sm text-gray-700 mt-2">
                      Current: "{outline.serp_features.featured_snippet.snippet.substring(0, 200)}..."
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* People Also Ask */}
          {outline.serp_features?.people_also_ask?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4 text-purple-800">
                People Also Ask (Must Answer)
              </h3>
              <div className="space-y-3">
                {outline.serp_features.people_also_ask.map((paa, idx) => (
                  <div key={idx} className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                    <p className="font-medium text-purple-900">{paa.question}</p>
                    {paa.snippet && (
                      <p className="text-sm text-gray-600 mt-2">
                        Current answer: {paa.snippet.substring(0, 150)}...
                      </p>
                    )}
                    {paa.source && (
                      <p className="text-xs text-gray-500 mt-1">Source: {paa.source}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related Searches */}
          {outline.serp_features?.related_searches?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4 text-blue-800">Related Searches</h3>
              <p className="text-sm text-gray-600 mb-3">
                Consider addressing these related topics for comprehensive coverage:
              </p>
              <div className="flex flex-wrap gap-2">
                {outline.serp_features.related_searches.map((search, idx) => (
                  <span key={idx} className="px-3 py-2 bg-blue-50 text-blue-800 rounded-lg text-sm border border-blue-200">
                    {search}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Content Strategy */}
          {outline.content_strategy && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Content Strategy</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Word Count - Show comparison for existing content */}
                <div className={`p-4 rounded-lg ${outline.optimization_mode ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50'}`}>
                  <p className="text-sm text-gray-600">Word Count</p>
                  {outline.optimization_mode && outline.content_strategy.word_count_current ? (
                    <>
                      <div className="flex items-baseline gap-2">
                        <p className="text-lg font-bold text-gray-500">{outline.content_strategy.word_count_current?.toLocaleString()}</p>
                        <span className="text-gray-400">→</span>
                        <p className="text-2xl font-bold text-[#223540]">{outline.content_strategy.word_count_target?.toLocaleString()}</p>
                      </div>
                      <p className={`text-xs font-medium mt-1 ${
                        outline.content_strategy.word_count_action === 'INCREASE' ? 'text-red-600' :
                        outline.content_strategy.word_count_action === 'DECREASE' ? 'text-orange-600' :
                        'text-green-600'
                      }`}>
                        {outline.content_strategy.word_count_action === 'INCREASE' && `+${outline.content_strategy.word_count_delta?.toLocaleString() || (outline.content_strategy.word_count_target - outline.content_strategy.word_count_current).toLocaleString()} words needed`}
                        {outline.content_strategy.word_count_action === 'DECREASE' && `Consider trimming ${Math.abs(outline.content_strategy.word_count_delta || 0).toLocaleString()} words`}
                        {outline.content_strategy.word_count_action === 'MAINTAIN' && 'Word count is competitive'}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-bold text-[#223540]">
                        {outline.content_strategy.target_word_count?.toLocaleString() || outline.word_count_target?.toLocaleString()}
                      </p>
                      {outline.content_strategy.min_word_count && (
                        <p className="text-xs text-gray-500">Min: {outline.content_strategy.min_word_count.toLocaleString()}</p>
                      )}
                    </>
                  )}
                </div>

                {/* Readability - Show comparison for existing content */}
                {(outline.content_strategy.readability_target || outline.content_strategy.readability_current) && (
                  <div className={`p-4 rounded-lg ${outline.optimization_mode ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50'}`}>
                    <p className="text-sm text-gray-600">Readability (Flesch)</p>
                    {outline.optimization_mode && outline.content_strategy.readability_current ? (
                      <>
                        <div className="flex items-baseline gap-2">
                          <p className="text-lg font-bold text-gray-500">{outline.content_strategy.readability_current}</p>
                          <span className="text-gray-400">→</span>
                          <p className="text-xl font-bold text-[#223540]">{outline.content_strategy.readability_target}</p>
                        </div>
                        <p className={`text-xs font-medium mt-1 ${
                          outline.content_strategy.readability_action === 'SIMPLIFY' ? 'text-red-600' :
                          outline.content_strategy.readability_action === 'ADD_DEPTH' ? 'text-orange-600' :
                          'text-green-600'
                        }`}>
                          {outline.content_strategy.readability_action === 'SIMPLIFY' && 'Simplify content - use shorter sentences'}
                          {outline.content_strategy.readability_action === 'ADD_DEPTH' && 'Add more technical depth'}
                          {outline.content_strategy.readability_action === 'MAINTAIN' && 'Readability is competitive'}
                        </p>
                      </>
                    ) : (
                      <p className="text-lg font-bold text-[#223540]">{outline.content_strategy.readability_target}</p>
                    )}
                  </div>
                )}
                {outline.content_strategy.schema_types?.length > 0 && (
                  <div className="p-4 bg-gray-50 rounded-lg col-span-2">
                    <p className="text-sm text-gray-600 mb-2">Schema Types to Implement</p>
                    <div className="flex flex-wrap gap-1">
                      {outline.content_strategy.schema_types.map((schema, idx) => (
                        <span key={idx} className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs">
                          {schema}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {outline.content_strategy.key_differentiators?.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Key Differentiators</p>
                  <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                    {outline.content_strategy.key_differentiators.map((diff, idx) => (
                      <li key={idx}>{diff}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Content Annotations - For Existing Content Optimization */}
          {outline.optimization_mode && outline.content_annotations?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-2 text-red-700">Content Improvements Needed</h3>
              <p className="text-sm text-gray-600 mb-4">
                Specific text changes to improve SEO performance. Prioritized by impact.
              </p>
              <div className="space-y-4">
                {outline.content_annotations.map((annotation, idx) => (
                  <div key={idx} className={`p-4 rounded-lg border-l-4 ${
                    annotation.priority === 'high' ? 'border-red-500 bg-red-50' :
                    annotation.priority === 'medium' ? 'border-orange-500 bg-orange-50' :
                    'border-yellow-500 bg-yellow-50'
                  }`}>
                    <div className="flex justify-between items-start mb-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        annotation.priority === 'high' ? 'bg-red-100 text-red-800' :
                        annotation.priority === 'medium' ? 'bg-orange-100 text-orange-800' :
                        'bg-yellow-100 text-yellow-800'
                      }`}>
                        {annotation.priority?.toUpperCase()} PRIORITY
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">ORIGINAL:</p>
                        <p className="text-sm text-gray-700 line-through bg-white p-2 rounded">{annotation.original_text}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-green-700 mb-1">IMPROVED:</p>
                        <p className="text-sm text-green-800 font-medium bg-green-100 p-2 rounded">{annotation.improved_text}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600 italic">{annotation.reason}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Questions to Answer */}
          {outline.questions_to_answer?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Questions to Answer</h3>
              <div className="space-y-3">
                {outline.questions_to_answer.map((q, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      q.priority === 'high' ? 'bg-red-100 text-red-800' :
                      q.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {q.priority}
                    </span>
                    <div className="flex-1">
                      <p className="font-medium">{q.question}</p>
                      <p className="text-sm text-gray-500">
                        Format: {q.format} | Place in: {q.placement}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Content Outline */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">
              {outline.optimization_mode ? 'Optimized Content Structure' : 'Content Outline'}
            </h3>
            {outline.optimization_mode && (
              <p className="text-sm text-gray-600 mb-4">
                Sections marked with status indicate what action to take with your existing content.
              </p>
            )}
            <div className="space-y-6">
              {outline.sections.map((section, idx) => (
                <div key={idx} className={`border-l-4 pl-4 ${
                  section.status === 'ADD' ? 'border-green-500 bg-green-50 rounded-r-lg pr-4 py-2' :
                  section.status === 'REMOVE' ? 'border-red-500 bg-red-50 rounded-r-lg pr-4 py-2' :
                  section.status === 'MODIFY' ? 'border-orange-500 bg-orange-50 rounded-r-lg pr-4 py-2' :
                  'border-[#223540]'
                }`}>
                  <div className="flex items-start justify-between">
                    <h4 className="text-lg font-semibold mb-2">
                      {idx + 1}. {section.heading}
                    </h4>
                    {section.status && (
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        section.status === 'ADD' ? 'bg-green-200 text-green-800' :
                        section.status === 'REMOVE' ? 'bg-red-200 text-red-800' :
                        section.status === 'MODIFY' ? 'bg-orange-200 text-orange-800' :
                        'bg-blue-200 text-blue-800'
                      }`}>
                        {section.status}
                      </span>
                    )}
                  </div>
                  {section.semantic_focus && (
                    <p className="text-sm text-gray-600 mb-2 italic">{section.semantic_focus}</p>
                  )}
                  <div className="text-sm text-gray-500 mb-2">
                    Target: {section.word_count_target?.toLocaleString() || 0} words
                  </div>

                  {section.h3_subsections?.length > 0 && (
                    <div className="mb-3">
                      <p className="text-sm font-medium text-gray-700">Subsections (H3):</p>
                      <ul className="list-disc list-inside text-sm text-gray-600 ml-4">
                        {section.h3_subsections.map((sub, i) => (
                          <li key={i}>{sub}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {section.key_points?.length > 0 && (
                    <div className="mb-3">
                      <p className="text-sm font-medium text-gray-700">Key Points:</p>
                      <ul className="list-disc list-inside text-sm text-gray-600 ml-4">
                        {section.key_points.map((point, i) => (
                          <li key={i}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {section.topics?.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {section.topics.map((topic, i) => (
                        <span key={i} className="px-2 py-1 bg-gray-100 rounded text-xs">
                          {topic}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Semantic Coverage */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Semantic Coverage</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {outline.topics?.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Must-Cover Topics</h4>
                  <div className="flex flex-wrap gap-2">
                    {outline.topics.map((topic, idx) => (
                      <span key={idx} className="px-3 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {outline.related_topics?.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Related Topics</h4>
                  <div className="flex flex-wrap gap-2">
                    {outline.related_topics.map((topic, idx) => (
                      <span key={idx} className="px-3 py-1 bg-gray-100 text-gray-800 rounded text-sm">
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {outline.entities?.length > 0 && (
                <div className="md:col-span-2">
                  <h4 className="font-medium text-gray-700 mb-2">Entities to Mention</h4>
                  <div className="flex flex-wrap gap-2">
                    {outline.entities.map((entity, idx) => (
                      <span key={idx} className="px-3 py-1 bg-green-100 text-green-800 rounded text-sm">
                        {entity}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* SERP Optimization & Competitive Gaps */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {outline.serp_optimization && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">SERP Optimization</h3>
                {outline.serp_optimization.featured_snippet_strategy && (
                  <div className="mb-4">
                    <h4 className="font-medium text-gray-700 mb-1">Featured Snippet Strategy</h4>
                    <p className="text-sm text-gray-600">{outline.serp_optimization.featured_snippet_strategy}</p>
                  </div>
                )}
                {outline.serp_optimization.faq_schema_questions?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-gray-700 mb-2">FAQ Schema Questions</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.serp_optimization.faq_schema_questions.map((q, idx) => (
                        <li key={idx}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {outline.serp_optimization.other_opportunities?.length > 0 && (
                  <div>
                    <h4 className="font-medium text-gray-700 mb-2">Other Opportunities</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.serp_optimization.other_opportunities.map((opp, idx) => (
                        <li key={idx}>{opp}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {outline.competitive_gaps && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">Competitive Gaps</h3>
                {/* New content format */}
                {outline.competitive_gaps.missing_from_competitors?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-gray-700 mb-2">Missing from Competitors</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.competitive_gaps.missing_from_competitors.map((gap, idx) => (
                        <li key={idx}>{gap}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {outline.competitive_gaps.unique_angles?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-gray-700 mb-2">Unique Angles</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.competitive_gaps.unique_angles.map((angle, idx) => (
                        <li key={idx}>{angle}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {outline.competitive_gaps.comprehensiveness_improvements?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-gray-700 mb-2">Comprehensiveness Improvements</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.competitive_gaps.comprehensiveness_improvements.map((imp, idx) => (
                        <li key={idx}>{imp}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {/* Optimization mode format */}
                {outline.competitive_gaps.missing_from_page?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-red-700 mb-2">Missing from Your Page</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.competitive_gaps.missing_from_page.map((gap, idx) => (
                        <li key={idx}>{gap}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {outline.competitive_gaps.strengths_to_keep?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-medium text-green-700 mb-2">Strengths to Keep</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.competitive_gaps.strengths_to_keep.map((strength, idx) => (
                        <li key={idx}>{strength}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {outline.competitive_gaps.quick_wins?.length > 0 && (
                  <div>
                    <h4 className="font-medium text-orange-700 mb-2">Quick Wins</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {outline.competitive_gaps.quick_wins.map((win, idx) => (
                        <li key={idx}>{win}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {keywords.length === 0 && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500">
            No selected keywords found. Go to Strategy Dashboard to select keywords first.
          </p>
        </div>
      )}
    </div>
  );
};

export default OutlineBuilder;
