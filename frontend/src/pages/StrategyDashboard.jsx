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
  // Row selection for scoring
  const [selectedForScoring, setSelectedForScoring] = useState(new Set());
  // Table filters
  const [filterTier, setFilterTier] = useState('all');
  const [filterScored, setFilterScored] = useState('all');
  const [filterSearch, setFilterSearch] = useState('');
  // Edit list settings
  const [showEditSettings, setShowEditSettings] = useState(false);
  const [editVertical, setEditVertical] = useState('');
  const [editVerticalKeywords, setEditVerticalKeywords] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);

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
      setSelectedForScoring(new Set()); // Clear selection when switching lists
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

  const handleScoreKeywords = async () => {
    if (!selectedList || selectedForScoring.size === 0) return;

    setScoring(true);
    setError('');

    try {
      const keywordIds = Array.from(selectedForScoring);
      await strategyAPI.scoreSelectedKeywords(selectedList.id, keywordIds);

      // Reload the full list to get all updated data
      await loadList(selectedList.id);

      // Clear selection after scoring
      setSelectedForScoring(new Set());
    } catch (err) {
      setError('Error scoring keywords: ' + (err.response?.data?.detail || err.message));
    } finally {
      setScoring(false);
    }
  };

  const handleSaveListSettings = async () => {
    if (!selectedList) return;
    setSavingSettings(true);
    setError('');

    try {
      const updates = {
        client_vertical: editVertical || null,
        client_vertical_keywords: editVerticalKeywords
          ? editVerticalKeywords.split('\n').map(k => k.trim()).filter(k => k)
          : null
      };
      await strategyAPI.updateList(selectedList.id, updates);
      await loadList(selectedList.id);
      setShowEditSettings(false);
    } catch (err) {
      setError('Error saving settings: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingSettings(false);
    }
  };

  const openEditSettings = () => {
    setEditVertical(selectedList?.client_profile?.vertical || '');
    setEditVerticalKeywords(selectedList?.client_profile?.vertical_keywords?.join('\n') || '');
    setShowEditSettings(true);
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
      ? ['Keyword', 'Win Score', 'Priority Tier', 'Domain Fit', 'Intent Fit', 'Forecast Score', 'Approved']
      : ['Keyword', 'Rankability Score', 'Tier', 'Approved'];

    const csv = [
      headers.join(','),
      ...selectedList.keywords.map(k => {
        if (hasClientProfile) {
          // Use composite tier as primary, derived from client_forecast
          const primaryTier = k.client_forecast ? k.client_forecast.tier : k.opportunity_tier;
          return [
            k.keyword,
            (k.rankability_score * 100).toFixed(1) + '%',
            primaryTier,
            k.domain_fit ? k.domain_fit.score.toFixed(1) + '%' : 'N/A',
            k.intent_fit ? k.intent_fit.score.toFixed(1) + '%' : 'N/A',
            k.client_forecast ? k.client_forecast.score.toFixed(1) + '%' : 'N/A',
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

  // Check if keyword is scored (has scored_at timestamp)
  const isKeywordScored = (keyword) => {
    // A keyword is scored if it has a forecast_pct OR rankability_score > 0
    // (scored_at is not returned in API response, so check actual score values)
    return (keyword.forecast_pct !== null && keyword.forecast_pct !== undefined) ||
           (keyword.rankability_score !== null && keyword.rankability_score > 0);
  };

  // Toggle selection for scoring
  const toggleScoringSelection = (keywordId) => {
    setSelectedForScoring(prev => {
      const newSet = new Set(prev);
      if (newSet.has(keywordId)) {
        newSet.delete(keywordId);
      } else {
        newSet.add(keywordId);
      }
      return newSet;
    });
  };

  // Select all visible keywords for scoring
  const selectAllForScoring = () => {
    const filteredIds = getFilteredKeywords().map(k => k.id);
    setSelectedForScoring(new Set(filteredIds));
  };

  // Clear all scoring selections
  const clearScoringSelection = () => {
    setSelectedForScoring(new Set());
  };

  // Filter keywords based on current filters
  const getFilteredKeywords = () => {
    if (!selectedList?.keywords) return [];

    return selectedList.keywords.filter(keyword => {
      // Search filter
      if (filterSearch && !keyword.keyword.toLowerCase().includes(filterSearch.toLowerCase())) {
        return false;
      }

      // Scored filter
      if (filterScored === 'scored' && !isKeywordScored(keyword)) {
        return false;
      }
      if (filterScored === 'unscored' && isKeywordScored(keyword)) {
        return false;
      }

      // Tier filter
      if (filterTier !== 'all') {
        const tier = selectedList.client_profile && keyword.client_forecast
          ? keyword.client_forecast.tier
          : keyword.opportunity_tier;
        if (tier !== filterTier) {
          return false;
        }
      }

      return true;
    });
  };

  const filteredKeywords = getFilteredKeywords();

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
              <div className="p-4 border-b">
                <div className="flex justify-between items-center mb-4">
                  <div>
                    <h2 className="text-xl font-semibold">{selectedList.name}</h2>
                    <p className="text-sm text-gray-600">{selectedList.target_domain_url}</p>
                    {selectedList.client_profile ? (
                      <p className="text-sm text-blue-600 mt-1">
                        Vertical: {VERTICALS.find(v => v.value === selectedList.client_profile.vertical)?.label || selectedList.client_profile.vertical}
                        {selectedList.client_profile.vertical_keywords?.length > 0 && (
                          <span className="text-gray-500"> ({selectedList.client_profile.vertical_keywords.length} topics)</span>
                        )}
                        <button
                          onClick={openEditSettings}
                          className="ml-2 text-xs text-gray-500 hover:text-gray-700 underline"
                        >
                          Edit
                        </button>
                      </p>
                    ) : (
                      <button
                        onClick={openEditSettings}
                        className="text-sm text-blue-600 hover:text-blue-700 mt-1"
                      >
                        + Add Client Profile
                      </button>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleScoreKeywords}
                      disabled={scoring || selectedForScoring.size === 0}
                      className="px-4 py-2 bg-[#223540] text-white rounded-md hover:bg-[#00a99d] disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Score selected keywords"
                    >
                      {scoring ? 'Scoring...' : `Score Keywords${selectedForScoring.size > 0 ? ` (${selectedForScoring.size})` : ''}`}
                    </button>
                    <button
                      onClick={handleExport}
                      className="px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"
                    >
                      Export CSV
                    </button>
                  </div>
                </div>

                {/* Edit Settings Modal */}
                {showEditSettings && (
                  <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <h3 className="font-medium text-gray-800 mb-3">Client Profile Settings</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Business Vertical</label>
                        <select
                          value={editVertical}
                          onChange={(e) => setEditVertical(e.target.value)}
                          className="w-full px-3 py-2 border rounded-md text-sm"
                        >
                          {VERTICALS.map(v => (
                            <option key={v.value} value={v.value}>{v.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Core Topics (one per line)</label>
                        <textarea
                          value={editVerticalKeywords}
                          onChange={(e) => setEditVerticalKeywords(e.target.value)}
                          placeholder="SEO services&#10;digital marketing&#10;content strategy"
                          rows={3}
                          className="w-full px-3 py-2 border rounded-md text-sm"
                        />
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={handleSaveListSettings}
                        disabled={savingSettings}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
                      >
                        {savingSettings ? 'Saving...' : 'Save Settings'}
                      </button>
                      <button
                        onClick={() => setShowEditSettings(false)}
                        className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md text-sm hover:bg-gray-400"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {/* Filter Controls */}
                <div className="flex flex-wrap gap-3 items-center">
                  <input
                    type="text"
                    placeholder="Search keywords..."
                    value={filterSearch}
                    onChange={(e) => setFilterSearch(e.target.value)}
                    className="px-3 py-1.5 border rounded text-sm w-48"
                  />
                  <select
                    value={filterScored}
                    onChange={(e) => setFilterScored(e.target.value)}
                    className="px-3 py-1.5 border rounded text-sm"
                  >
                    <option value="all">All Keywords</option>
                    <option value="scored">Scored Only</option>
                    <option value="unscored">Unscored Only</option>
                  </select>
                  <select
                    value={filterTier}
                    onChange={(e) => setFilterTier(e.target.value)}
                    className="px-3 py-1.5 border rounded text-sm"
                  >
                    <option value="all">All Tiers</option>
                    {selectedList.client_profile ? (
                      <>
                        <option value="HIGH_PRIORITY">High Priority</option>
                        <option value="GOOD_FIT">Good Fit</option>
                        <option value="CONSIDER">Consider</option>
                        <option value="LONG_TERM">Long Term</option>
                        <option value="NOT_RECOMMENDED">Not Recommended</option>
                      </>
                    ) : (
                      <>
                        <option value="T1_GO_NOW">T1 - Go Now</option>
                        <option value="T2_STRATEGIC">T2 - Strategic</option>
                        <option value="T3_LONG_GAME">T3 - Long Game</option>
                        <option value="T4_NOT_WORTH_IT">T4 - Not Worth It</option>
                      </>
                    )}
                  </select>
                  <span className="text-sm text-gray-500">
                    Showing {filteredKeywords.length} of {selectedList.keywords?.length || 0} keywords
                  </span>
                  {selectedForScoring.size > 0 && (
                    <button
                      onClick={clearScoringSelection}
                      className="text-sm text-gray-500 hover:text-gray-700 underline"
                    >
                      Clear selection
                    </button>
                  )}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-10">
                        <div className="flex flex-col items-start gap-1">
                          <span className="text-xs font-medium text-gray-600 whitespace-nowrap">Select to Score</span>
                          <input
                            type="checkbox"
                            checked={filteredKeywords.length > 0 && filteredKeywords.every(k => selectedForScoring.has(k.id))}
                            onChange={(e) => e.target.checked ? selectAllForScoring() : clearScoringSelection()}
                            className="h-4 w-4"
                            title="Select all for scoring"
                          />
                        </div>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keyword</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        <div className="relative inline-block group">
                          <span className="flex items-center gap-1 cursor-help">
                            Win Score
                            <svg className="w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                            </svg>
                          </span>
                          <div className="absolute left-0 top-full mt-1 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 font-normal normal-case">
                            Probability of ranking in Top 10 based on your site's authority vs SERP competition
                          </div>
                        </div>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        <div className="relative inline-block group">
                          <span className="flex items-center gap-1 cursor-help">
                            Tier
                            <svg className="w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                            </svg>
                          </span>
                          <div className="absolute left-0 top-full mt-1 w-72 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 font-normal normal-case">
                            {selectedList.client_profile ? (
                              <>Composite priority (40% Win + 35% Domain + 25% Intent): <span className="text-green-400">High</span> ≥70 · <span className="text-blue-400">Good</span> 50-69 · <span className="text-yellow-400">Consider</span> 35-49 · <span className="text-orange-400">Long Term</span> 20-34 · <span className="text-red-400">Not Rec</span> &lt;20</>
                            ) : (
                              <>Win score ranking: <span className="text-green-400">T1</span> ≥20% · <span className="text-blue-400">T2</span> 10-19% · <span className="text-yellow-400">T3</span> 4-9% · <span className="text-red-400">T4</span> &lt;4%</>
                            )}
                          </div>
                        </div>
                      </th>
                      {selectedList.client_profile && (
                        <>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            <div className="relative inline-block group">
                              <span className="flex items-center gap-1 cursor-help">
                                Domain Fit
                                <svg className="w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                </svg>
                              </span>
                              <div className="absolute left-0 top-full mt-1 w-56 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 font-normal normal-case">
                                How your domain authority compares to SERP competitors (0-100%)
                              </div>
                            </div>
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            <div className="relative inline-block group">
                              <span className="flex items-center gap-1 cursor-help">
                                Intent Fit
                                <svg className="w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                </svg>
                              </span>
                              <div className="absolute left-0 top-full mt-1 w-56 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 font-normal normal-case">
                                How well keyword matches your business vertical (0-100%)
                              </div>
                            </div>
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                            <div className="relative inline-block group">
                              <span className="flex items-center gap-1 cursor-help">
                                Forecast
                                <svg className="w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                </svg>
                              </span>
                              <div className="absolute left-0 top-full mt-1 w-56 p-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 font-normal normal-case">
                                Combined score: 40% Win Score + 35% Domain Fit + 25% Intent Fit
                              </div>
                            </div>
                          </th>
                        </>
                      )}
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Approved</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Remove</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredKeywords
                      .sort((a, b) => {
                        // Unscored keywords go to top, then sort by rankability score
                        const aScored = isKeywordScored(a);
                        const bScored = isKeywordScored(b);
                        if (aScored !== bScored) return aScored ? 1 : -1;
                        return b.rankability_score - a.rankability_score;
                      })
                      .map(keyword => (
                        <tr key={keyword.id} className={selectedForScoring.has(keyword.id) ? 'bg-blue-50' : ''}>
                          <td className="px-3 py-4 whitespace-nowrap">
                            <input
                              type="checkbox"
                              checked={selectedForScoring.has(keyword.id)}
                              onChange={() => toggleScoringSelection(keyword.id)}
                              className="h-4 w-4"
                              title="Select for scoring"
                            />
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm font-medium">{keyword.keyword}</td>
                          <td className="px-4 py-4 whitespace-nowrap text-sm">
                            {isKeywordScored(keyword) ? (
                              <span className="font-medium">
                                {keyword.forecast_pct !== null && keyword.forecast_pct !== undefined
                                  ? `${keyword.forecast_pct.toFixed(1)}%`
                                  : `${(keyword.rankability_score * 100).toFixed(1)}%`}
                              </span>
                            ) : (
                              <span className="text-gray-400 italic text-xs">Run to get scores</span>
                            )}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap">
                            {isKeywordScored(keyword) ? (
                              /* Show composite forecast tier if client profile exists and client_forecast available */
                              selectedList.client_profile && keyword.client_forecast ? (
                                <span className={`px-2 py-1 rounded text-xs font-medium ${getClientForecastColor(keyword.client_forecast.tier)}`}>
                                  {getClientForecastDisplayName(keyword.client_forecast.tier)}
                                </span>
                              ) : (
                                <span className={`px-2 py-1 rounded text-xs font-medium ${getTierColor(keyword.opportunity_tier)}`}>
                                  {getTierDisplayName(keyword.opportunity_tier)}
                                </span>
                              )
                            ) : (
                              <span className="text-gray-400 italic text-xs">-</span>
                            )}
                          </td>
                          {/* Fit score columns - only show if client profile exists */}
                          {selectedList.client_profile && (
                            <>
                              <td className="px-4 py-4 whitespace-nowrap">
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
                              <td className="px-4 py-4 whitespace-nowrap">
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
                              <td className="px-4 py-4 whitespace-nowrap">
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
                          <td className="px-4 py-4 whitespace-nowrap">
                            <input
                              type="checkbox"
                              checked={keyword.is_selected}
                              onChange={(e) => handleUpdateKeyword(keyword.id, { is_selected: e.target.checked })}
                              className="h-4 w-4"
                              title="Approve this keyword for content builder"
                            />
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap">
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

