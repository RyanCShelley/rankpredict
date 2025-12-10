import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { strategyAPI } from '../services/api';

// Available verticals for client profile
const VERTICALS = [
  { value: '', label: 'Select a vertical...' },
  { value: 'defense', label: 'Defense Contractors' },
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'finance', label: 'Finance' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'home_services', label: 'Home Services' },
  { value: 'legal', label: 'Legal' },
  { value: 'local_business', label: 'Local Business' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'saas', label: 'SaaS' },
];

const StrategyDashboard = () => {
  const navigate = useNavigate();
  const [lists, setLists] = useState([]);
  const [selectedList, setSelectedList] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showAddKeywordsForm, setShowAddKeywordsForm] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [newTargetDomain, setNewTargetDomain] = useState('');
  const [newKeywords, setNewKeywords] = useState('');
  const [keywordsToAdd, setKeywordsToAdd] = useState('');
  // Client profile fields
  const [clientVertical, setClientVertical] = useState('');
  const [clientVerticalKeywords, setClientVerticalKeywords] = useState('');
  const [loading, setLoading] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [deletingList, setDeletingList] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadLists();
  }, []);

  const loadLists = async () => {
    try {
      const data = await strategyAPI.getLists();
      setLists(data);
    } catch (err) {
      console.error('Error loading lists:', err);
    }
  };

  const loadList = async (listId) => {
    try {
      const data = await strategyAPI.getList(listId);
      setSelectedList(data);
      setShowCreateForm(false);
    } catch (err) {
      setError('Error loading list: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleCreateList = async (e) => {
    e.preventDefault();
    if (!newListName.trim() || !newTargetDomain.trim() || !newKeywords.trim()) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const keywords = newKeywords.split('\n').map(k => k.trim()).filter(k => k.length > 0);
      // Build client profile if vertical is selected
      let clientProfile = null;
      if (clientVertical) {
        const verticalKeywordsList = clientVerticalKeywords
          .split('\n')
          .map(k => k.trim())
          .filter(k => k.length > 0);
        clientProfile = {
          vertical: clientVertical,
          vertical_keywords: verticalKeywordsList.length > 0 ? verticalKeywordsList : null
        };
      }
      const data = await strategyAPI.createList(newListName, newTargetDomain, keywords, clientProfile);
      setSelectedList(data);
      setShowCreateForm(false);
      setNewListName('');
      setNewTargetDomain('');
      setNewKeywords('');
      setClientVertical('');
      setClientVerticalKeywords('');
      await loadLists();
    } catch (err) {
      setError('Error creating list: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleScoreKeywords = async (forceRescore = false) => {
    if (!selectedList) return;

    setScoring(true);
    setError('');

    try {
      const data = await strategyAPI.scoreKeywords(selectedList.id, forceRescore);
      // Update selectedList with scored keywords directly (preserves fit scores)
      setSelectedList(prev => ({
        ...prev,
        keywords: data.keywords
      }));
    } catch (err) {
      setError('Error scoring keywords: ' + (err.response?.data?.detail || err.message));
    } finally {
      setScoring(false);
    }
  };

  const handleUpdateKeyword = async (keywordId, updates) => {
    try {
      await strategyAPI.updateKeyword(keywordId, updates);
      // Reload list to get updated data
      await loadList(selectedList.id);
    } catch (err) {
      setError('Error updating keyword: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteKeyword = async (keywordId) => {
    if (!window.confirm('Are you sure you want to remove this keyword from the list?')) {
      return;
    }
    try {
      await strategyAPI.deleteKeyword(keywordId);
      // Reload list to get updated data
      await loadList(selectedList.id);
    } catch (err) {
      setError('Error deleting keyword: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleAddKeywords = async (e) => {
    e.preventDefault();
    if (!keywordsToAdd.trim() || !selectedList) {
      setError('Please enter keywords to add');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const keywords = keywordsToAdd.split('\n').map(k => k.trim()).filter(k => k.length > 0);
      const data = await strategyAPI.addKeywords(selectedList.id, keywords);
      setSelectedList(data);
      setShowAddKeywordsForm(false);
      setKeywordsToAdd('');
      await loadLists();
    } catch (err) {
      setError('Error adding keywords: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteList = async (listId) => {
    if (!window.confirm('Are you sure you want to delete this keyword list? This action cannot be undone.')) {
      return;
    }

    setDeletingList(true);
    setError('');

    try {
      await strategyAPI.deleteList(listId);
      setSelectedList(null);
      await loadLists();
    } catch (err) {
      setError('Error deleting list: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDeletingList(false);
    }
  };

  const handleExport = () => {
    if (!selectedList || !selectedList.keywords) return;

    const hasClientProfile = selectedList.client_profile;
    const headers = hasClientProfile
      ? ['Keyword', 'Win Score', 'Tier', 'Domain Fit', 'Intent Fit', 'Client Forecast', 'Forecast Tier', 'Approved']
      : ['Keyword', 'Rankability Score', 'Tier', 'Approved'];

    const csv = [
      headers.join(','),
      ...selectedList.keywords.map(k => {
        if (hasClientProfile) {
          return [
            k.keyword,
            (k.rankability_score * 100).toFixed(1) + '%',
            k.opportunity_tier,
            k.domain_fit ? k.domain_fit.score.toFixed(1) + '%' : 'N/A',
            k.intent_fit ? k.intent_fit.score.toFixed(1) + '%' : 'N/A',
            k.client_forecast ? k.client_forecast.score.toFixed(1) + '%' : 'N/A',
            k.client_forecast ? k.client_forecast.tier : 'N/A',
            k.is_selected ? 'Yes' : 'No'
          ].join(',');
        } else {
          return [
            k.keyword,
            (k.rankability_score * 100).toFixed(1) + '%',
            k.opportunity_tier,
            k.is_selected ? 'Yes' : 'No'
          ].join(',');
        }
      })
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedList.name}_keywords.csv`;
    a.click();
  };

  const getTierColor = (tier) => {
    switch (tier) {
      case 'T1_GO_NOW': return 'bg-green-100 text-green-800';
      case 'T2_STRATEGIC': return 'bg-blue-100 text-blue-800';
      case 'T3_LONG_GAME': return 'bg-yellow-100 text-yellow-800';
      case 'T4_NOT_WORTH_IT': return 'bg-red-100 text-red-800';
      // Legacy tiers for backward compatibility
      case 'HIGH': return 'bg-green-100 text-green-800';
      case 'MEDIUM': return 'bg-yellow-100 text-yellow-800';
      case 'LOW': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTierDisplayName = (tier) => {
    switch (tier) {
      case 'T1_GO_NOW': return 'T1 - Go Now';
      case 'T2_STRATEGIC': return 'T2 - Strategic';
      case 'T3_LONG_GAME': return 'T3 - Long Game';
      case 'T4_NOT_WORTH_IT': return 'T4 - Not Worth It';
      default: return tier;
    }
  };

  // Client forecast tier colors and display names
  const getClientForecastColor = (tier) => {
    switch (tier) {
      case 'HIGH_PRIORITY': return 'bg-green-100 text-green-800';
      case 'GOOD_FIT': return 'bg-blue-100 text-blue-800';
      case 'CONSIDER': return 'bg-yellow-100 text-yellow-800';
      case 'LONG_TERM': return 'bg-orange-100 text-orange-800';
      case 'NOT_RECOMMENDED': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getClientForecastDisplayName = (tier) => {
    switch (tier) {
      case 'HIGH_PRIORITY': return 'High Priority';
      case 'GOOD_FIT': return 'Good Fit';
      case 'CONSIDER': return 'Consider';
      case 'LONG_TERM': return 'Long Term';
      case 'NOT_RECOMMENDED': return 'Not Recommended';
      default: return tier;
    }
  };

  // Fit score color helper (0-100 scale)
  const getFitScoreColor = (score) => {
    if (score >= 70) return 'text-green-600';
    if (score >= 50) return 'text-blue-600';
    if (score >= 30) return 'text-yellow-600';
    return 'text-red-600';
  };

  const selectedCount = selectedList?.keywords?.filter(k => k.is_selected).length || 0;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Strategy Dashboard</h1>
        <button
          onClick={() => navigate('/outline')}
          disabled={selectedCount === 0}
          className="px-4 py-2 bg-[#223540] text-white rounded-md hover:bg-[#00a99d] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Go to Outline Builder {selectedCount > 0 && `(${selectedCount} selected)`}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar - Lists */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Keyword Lists</h2>
              <button
                onClick={() => setShowCreateForm(true)}
                className="text-sm px-3 py-1 bg-[#223540] text-white rounded hover:bg-[#00a99d]"
              >
                + New
              </button>
            </div>

            {selectedList && (
              <div className="mb-4 space-y-2">
                <button
                  onClick={() => setShowAddKeywordsForm(true)}
                  className="w-full text-sm px-3 py-2 bg-green-500 text-white rounded hover:bg-green-600"
                >
                  + Add Keywords
                </button>
                <button
                  onClick={() => handleDeleteList(selectedList.id)}
                  disabled={deletingList}
                  className="w-full text-sm px-3 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
                >
                  {deletingList ? 'Deleting...' : 'Delete List'}
                </button>
              </div>
            )}

            {showAddKeywordsForm && selectedList && (
              <form onSubmit={handleAddKeywords} className="mb-4 space-y-3 p-3 bg-gray-50 rounded">
                <h3 className="font-medium text-sm">Add Keywords to {selectedList.name}</h3>
                <textarea
                  placeholder="Keywords (one per line)"
                  value={keywordsToAdd}
                  onChange={(e) => setKeywordsToAdd(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-sm"
                  rows={5}
                  required
                />
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
                  >
                    {loading ? 'Adding...' : 'Add Keywords'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddKeywordsForm(false);
                      setKeywordsToAdd('');
                    }}
                    className="px-3 py-1 bg-gray-300 rounded text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            {showCreateForm && (
              <form onSubmit={handleCreateList} className="mb-4 space-y-3 p-3 bg-gray-50 rounded">
                <input
                  type="text"
                  placeholder="List name"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-sm"
                  required
                />
                <input
                  type="url"
                  placeholder="Target domain URL"
                  value={newTargetDomain}
                  onChange={(e) => setNewTargetDomain(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-sm"
                  required
                />
                <textarea
                  placeholder="Keywords (one per line)"
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-sm"
                  rows={5}
                  required
                />
                {/* Client Profile Section */}
                <div className="border-t pt-3 mt-3">
                  <p className="text-xs font-medium text-gray-600 mb-2">Client Profile (Optional - for Fit Scores)</p>
                  <select
                    value={clientVertical}
                    onChange={(e) => setClientVertical(e.target.value)}
                    className="w-full px-2 py-1 border rounded text-sm mb-2"
                  >
                    {VERTICALS.map(v => (
                      <option key={v.value} value={v.value}>{v.label}</option>
                    ))}
                  </select>
                  {clientVertical && (
                    <textarea
                      placeholder="Vertical keywords (one per line, e.g., 'personal injury lawyer', 'car accident attorney')"
                      value={clientVerticalKeywords}
                      onChange={(e) => setClientVerticalKeywords(e.target.value)}
                      className="w-full px-2 py-1 border rounded text-sm"
                      rows={3}
                    />
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 px-3 py-1 bg-[#223540] text-white rounded text-sm hover:bg-[#00a99d]"
                  >
                    {loading ? 'Creating...' : 'Create'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateForm(false);
                      setNewListName('');
                      setNewTargetDomain('');
                      setNewKeywords('');
                      setClientVertical('');
                      setClientVerticalKeywords('');
                    }}
                    className="px-3 py-1 bg-gray-300 rounded text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            <div className="space-y-2">
              {lists.map(list => (
                <div key={list.id} className="flex items-center gap-2">
                  <button
                    onClick={() => loadList(list.id)}
                    className={`flex-1 text-left px-3 py-2 rounded text-sm ${
                      selectedList?.id === list.id
                        ? 'bg-[#223540] text-white'
                        : 'bg-gray-100 hover:bg-gray-200'
                    }`}
                  >
                    <div className="font-medium">{list.name}</div>
                    <div className="text-xs opacity-75">{list.keyword_count} keywords</div>
                  </button>
                  {selectedList?.id !== list.id && (
                    <button
                      onClick={() => handleDeleteList(list.id)}
                      disabled={deletingList}
                      className="px-2 py-1 text-red-500 hover:bg-red-50 rounded text-xs"
                      title="Delete list"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content - Keywords */}
        <div className="lg:col-span-3">
          {selectedList ? (
            <div className="bg-white rounded-lg shadow">
              <div className="p-4 border-b flex justify-between items-center">
                <div>
                  <h2 className="text-xl font-semibold">{selectedList.name}</h2>
                  <p className="text-sm text-gray-600">{selectedList.target_domain_url}</p>
                  {selectedList.client_profile && (
                    <p className="text-sm text-blue-600 mt-1">
                      Vertical: {VERTICALS.find(v => v.value === selectedList.client_profile.vertical)?.label || selectedList.client_profile.vertical}
                      {selectedList.client_profile.vertical_keywords?.length > 0 && (
                        <span className="text-gray-500"> ({selectedList.client_profile.vertical_keywords.length} keywords)</span>
                      )}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleScoreKeywords(false)}
                    disabled={scoring}
                    className="px-4 py-2 bg-[#223540] text-white rounded-md hover:bg-[#00a99d] disabled:opacity-50"
                    title="Score only new/unscored keywords"
                  >
                    {scoring ? 'Scoring...' : 'Score New'}
                  </button>
                  <button
                    onClick={() => handleScoreKeywords(true)}
                    disabled={scoring}
                    className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 disabled:opacity-50"
                    title="Re-score all keywords (fresh SERP data)"
                  >
                    {scoring ? 'Scoring...' : 'Re-Score All'}
                  </button>
                  <button
                    onClick={handleExport}
                    className="px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"
                  >
                    Export CSV
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keyword</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Win Score</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tier</th>
                      {selectedList.client_profile && (
                        <>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Domain Fit</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Intent Fit</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Forecast</th>
                        </>
                      )}
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Approved</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Remove</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {selectedList.keywords
                      .sort((a, b) => b.rankability_score - a.rankability_score)
                      .map(keyword => (
                        <tr key={keyword.id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{keyword.keyword}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <div className="flex items-center gap-2">
                              <span className="font-medium">
                                {keyword.forecast_pct !== null && keyword.forecast_pct !== undefined
                                  ? `${keyword.forecast_pct.toFixed(1)}%`
                                  : `${(keyword.rankability_score * 100).toFixed(1)}%`}
                              </span>
                              <div className="relative inline-block group">
                                <svg
                                  className="w-4 h-4 text-gray-400 hover:text-gray-600 cursor-help"
                                  fill="currentColor"
                                  viewBox="0 0 20 20"
                                  xmlns="http://www.w3.org/2000/svg"
                                >
                                  <path
                                    fillRule="evenodd"
                                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11.718-1.197A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
                                    clipRule="evenodd"
                                  />
                                </svg>
                                {keyword.tier_explanation && (
                                  <div className="absolute left-0 bottom-full mb-2 w-80 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                                    <div className="font-semibold mb-2 text-sm">
                                      {getTierDisplayName(keyword.opportunity_tier)}
                                      {keyword.forecast_pct !== null && keyword.forecast_pct !== undefined && (
                                        <span className="ml-2 text-gray-300">({keyword.forecast_pct.toFixed(1)}%)</span>
                                      )}
                                    </div>
                                    <div className="text-gray-200">{keyword.tier_explanation}</div>
                                    <div className="absolute bottom-0 left-4 transform translate-y-full">
                                      <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${getTierColor(keyword.opportunity_tier)}`}>
                              {getTierDisplayName(keyword.opportunity_tier)}
                            </span>
                          </td>
                          {/* Fit score columns - only show if client profile exists */}
                          {selectedList.client_profile && (
                            <>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {keyword.domain_fit ? (
                                  <div className="relative inline-block group">
                                    <span className={`font-medium ${getFitScoreColor(keyword.domain_fit.score)}`}>
                                      {keyword.domain_fit.score.toFixed(1)}%
                                    </span>
                                    <div className="absolute left-0 bottom-full mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                                      {keyword.domain_fit.explanation}
                                    </div>
                                  </div>
                                ) : (
                                  <span className="text-gray-400">-</span>
                                )}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {keyword.intent_fit ? (
                                  <div className="relative inline-block group">
                                    <span className={`font-medium ${getFitScoreColor(keyword.intent_fit.score)}`}>
                                      {keyword.intent_fit.score.toFixed(1)}%
                                    </span>
                                    <div className="absolute left-0 bottom-full mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                                      {keyword.intent_fit.explanation}
                                    </div>
                                  </div>
                                ) : (
                                  <span className="text-gray-400">-</span>
                                )}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {keyword.client_forecast ? (
                                  <div className="relative inline-block group">
                                    <span className={`px-2 py-1 rounded text-xs font-medium ${getClientForecastColor(keyword.client_forecast.tier)}`}>
                                      {keyword.client_forecast.score.toFixed(1)}%
                                    </span>
                                    <div className="absolute left-0 bottom-full mb-2 w-80 p-3 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                                      <div className="font-semibold mb-1">{getClientForecastDisplayName(keyword.client_forecast.tier)}</div>
                                      <div className="text-gray-200">{keyword.client_forecast.recommendation}</div>
                                    </div>
                                  </div>
                                ) : (
                                  <span className="text-gray-400">-</span>
                                )}
                              </td>
                            </>
                          )}
                          <td className="px-6 py-4 whitespace-nowrap">
                            <input
                              type="checkbox"
                              checked={keyword.is_selected}
                              onChange={(e) => handleUpdateKeyword(keyword.id, { is_selected: e.target.checked })}
                              className="h-4 w-4"
                              title="Approve this keyword for content builder"
                            />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <button
                              onClick={() => handleDeleteKeyword(keyword.id)}
                              className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                              title="Remove keyword from list"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Metrics Explanation Section */}
              <div className="p-6 bg-gray-50 border-t">
                {/* Core Metrics */}
                <h3 className="text-lg font-semibold mb-4">Understanding the Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <h4 className="font-semibold text-[#223540] mb-2">Win Score</h4>
                    <p className="text-sm text-gray-600">
                      The probability (0-100%) that your target domain can rank in the Top 10 for this keyword.
                      Based on comparing your site's authority metrics against the current SERP competitors,
                      factoring in Domain Trust, referring domains, and SERP competitive gravity.
                    </p>
                  </div>

                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <h4 className="font-semibold text-[#223540] mb-2">Tier</h4>
                    <p className="text-sm text-gray-600">
                      A categorical ranking of keyword opportunity based on Win Score:
                      <span className="block mt-1"><span className="text-green-600 font-medium">T1 Go Now</span> (≥20%) - High probability, prioritize now</span>
                      <span className="block"><span className="text-blue-600 font-medium">T2 Strategic</span> (10-19.9%) - Achievable with effort</span>
                      <span className="block"><span className="text-yellow-600 font-medium">T3 Long Game</span> (4-9.9%) - Requires authority growth</span>
                      <span className="block"><span className="text-red-600 font-medium">T4 Not Worth It</span> (&lt;4%) - Skip or find alternatives</span>
                    </p>
                  </div>

                  {selectedList?.client_profile && (
                    <>
                      <div className="bg-white p-4 rounded-lg border border-purple-200">
                        <h4 className="font-semibold text-purple-700 mb-2">Domain Fit</h4>
                        <p className="text-sm text-gray-600">
                          How well your domain's authority matches the SERP competition (0-100%).
                          Compares your Domain Trust and referring domains against SERP medians.
                          Higher = your authority is competitive for this keyword.
                        </p>
                        <div className="mt-2 text-xs text-gray-500">
                          <span className="text-green-600">≥70% Strong</span> |
                          <span className="text-blue-600"> 50-69% Good</span> |
                          <span className="text-yellow-600"> 30-49% Weak</span> |
                          <span className="text-red-600"> &lt;30% Poor</span>
                        </div>
                      </div>

                      <div className="bg-white p-4 rounded-lg border border-indigo-200">
                        <h4 className="font-semibold text-indigo-700 mb-2">Intent Fit</h4>
                        <p className="text-sm text-gray-600">
                          How well the keyword matches your client's business vertical (0-100%).
                          Based on keyword pattern matching against industry-specific terms
                          and semantic similarity to your vertical keywords.
                        </p>
                        <div className="mt-2 text-xs text-gray-500">
                          <span className="text-green-600">≥70% Perfect match</span> |
                          <span className="text-blue-600"> 50-69% Good fit</span> |
                          <span className="text-yellow-600"> 30-49% Partial</span> |
                          <span className="text-red-600"> &lt;30% Poor fit</span>
                        </div>
                      </div>

                      <div className="bg-white p-4 rounded-lg border border-teal-200">
                        <h4 className="font-semibold text-teal-700 mb-2">Forecast</h4>
                        <p className="text-sm text-gray-600">
                          Combined client-specific success score (0-100%) weighing:
                          <span className="block mt-1">• 40% Win Score (can you rank?)</span>
                          <span className="block">• 35% Domain Fit (authority match)</span>
                          <span className="block">• 25% Intent Fit (business relevance)</span>
                        </p>
                        <div className="mt-2 text-xs text-gray-500">
                          <span className="text-green-600">≥70% High Priority</span> |
                          <span className="text-blue-600"> 50-69% Good Fit</span> |
                          <span className="text-yellow-600"> 35-49% Consider</span> |
                          <span className="text-orange-600"> 20-34% Long Term</span> |
                          <span className="text-red-600"> &lt;20% Not Recommended</span>
                        </div>
                      </div>
                    </>
                  )}
                </div>

              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500">Select a keyword list or create a new one to get started</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StrategyDashboard;

