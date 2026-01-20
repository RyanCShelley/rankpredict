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
  const [fetchingVolumes, setFetchingVolumes] = useState(false);
  const [error, setError] = useState('');
  // Row selection for scoring
  const [selectedForScoring, setSelectedForScoring] = useState(new Set());
  // Table filters
  const [filterTier, setFilterTier] = useState('all');
  const [filterScored, setFilterScored] = useState('all');
  const [filterSearch, setFilterSearch] = useState('');
  // Sorting
  const [sortColumn, setSortColumn] = useState('keyword');
  const [sortDirection, setSortDirection] = useState('asc');
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
      setSelectedForScoring(new Set());
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
      await loadList(selectedList.id);
      setSelectedForScoring(new Set());
    } catch (err) {
      setError('Error scoring keywords: ' + (err.response?.data?.detail || err.message));
    } finally {
      setScoring(false);
    }
  };

  const handleFetchVolumes = async () => {
    if (!selectedList) return;

    setFetchingVolumes(true);
    setError('');

    try {
      const result = await strategyAPI.fetchVolumes(selectedList.id);
      await loadList(selectedList.id);
      if (result.keywords_updated === 0) {
        setError('All keywords already have volume data');
      }
    } catch (err) {
      setError('Error fetching volumes: ' + (err.response?.data?.detail || err.message));
    } finally {
      setFetchingVolumes(false);
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
      await loadList(selectedList.id);
    } catch (err) {
      setError('Error updating keyword: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteKeyword = async (keywordId) => {
    try {
      await strategyAPI.deleteKeyword(keywordId);
      await loadList(selectedList.id);
    } catch (err) {
      setError('Error deleting keyword: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleActionChange = async (keywordId, action) => {
    if (action === 'remove') {
      if (!window.confirm('Are you sure you want to remove this keyword?')) {
        return;
      }
      await handleDeleteKeyword(keywordId);
    } else {
      await handleUpdateKeyword(keywordId, { action_status: action });
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

    const headers = ['Keyword', 'Volume', 'Tier', 'Forecast', 'Action'];
    const csv = [
      headers.join(','),
      ...selectedList.keywords.map(k => {
        const tier = k.client_forecast ? k.client_forecast.tier : k.opportunity_tier;
        const forecast = k.client_forecast ? k.client_forecast.score : (k.rankability_score * 100);
        return [
          `"${k.keyword}"`,
          k.volume || '',
          tier,
          forecast ? forecast.toFixed(1) + '%' : '',
          k.action_status || 'none'
        ].join(',');
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
      case 'HIGH_PRIORITY': return 'bg-green-100 text-green-800';
      case 'GOOD_FIT': return 'bg-blue-100 text-blue-800';
      case 'CONSIDER': return 'bg-yellow-100 text-yellow-800';
      case 'LONG_TERM': return 'bg-orange-100 text-orange-800';
      case 'NOT_RECOMMENDED': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTierDisplayName = (tier) => {
    switch (tier) {
      case 'T1_GO_NOW': return 'T1';
      case 'T2_STRATEGIC': return 'T2';
      case 'T3_LONG_GAME': return 'T3';
      case 'T4_NOT_WORTH_IT': return 'T4';
      case 'HIGH_PRIORITY': return 'High';
      case 'GOOD_FIT': return 'Good';
      case 'CONSIDER': return 'Consider';
      case 'LONG_TERM': return 'Long';
      case 'NOT_RECOMMENDED': return 'Not Rec';
      default: return tier || '-';
    }
  };

  const getActionColor = (action) => {
    switch (action) {
      case 'approved': return 'bg-green-100 text-green-800 border-green-300';
      case 'whole': return 'bg-blue-100 text-blue-800 border-blue-300';
      default: return 'bg-gray-50 text-gray-600 border-gray-300';
    }
  };

  const selectedCount = selectedList?.keywords?.filter(k => k.action_status === 'approved').length || 0;

  const isKeywordScored = (keyword) => {
    return (keyword.forecast_pct !== null && keyword.forecast_pct !== undefined) ||
           (keyword.rankability_score !== null && keyword.rankability_score > 0);
  };

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

  const selectAllForScoring = () => {
    const filteredIds = getFilteredKeywords().map(k => k.id);
    setSelectedForScoring(new Set(filteredIds));
  };

  const clearScoringSelection = () => {
    setSelectedForScoring(new Set());
  };

  // Sorting handler
  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Sort indicator
  const SortIndicator = ({ column }) => {
    if (sortColumn !== column) {
      return <span className="text-gray-300 ml-1">↕</span>;
    }
    return <span className="text-gray-600 ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>;
  };

  // Filter keywords
  const getFilteredKeywords = () => {
    if (!selectedList?.keywords) return [];

    return selectedList.keywords.filter(keyword => {
      if (filterSearch && !keyword.keyword.toLowerCase().includes(filterSearch.toLowerCase())) {
        return false;
      }
      if (filterScored === 'scored' && !isKeywordScored(keyword)) {
        return false;
      }
      if (filterScored === 'unscored' && isKeywordScored(keyword)) {
        return false;
      }
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

  // Sort and filter keywords
  const getSortedKeywords = () => {
    const filtered = getFilteredKeywords();

    return filtered.sort((a, b) => {
      let aVal, bVal;

      switch (sortColumn) {
        case 'keyword':
          aVal = a.keyword.toLowerCase();
          bVal = b.keyword.toLowerCase();
          break;
        case 'volume':
          aVal = a.volume || 0;
          bVal = b.volume || 0;
          break;
        case 'tier':
          const tierOrder = {
            'T1_GO_NOW': 1, 'HIGH_PRIORITY': 1,
            'T2_STRATEGIC': 2, 'GOOD_FIT': 2,
            'T3_LONG_GAME': 3, 'CONSIDER': 3,
            'T4_NOT_WORTH_IT': 4, 'LONG_TERM': 4, 'NOT_RECOMMENDED': 5
          };
          const aTier = a.client_forecast?.tier || a.opportunity_tier;
          const bTier = b.client_forecast?.tier || b.opportunity_tier;
          aVal = tierOrder[aTier] || 99;
          bVal = tierOrder[bTier] || 99;
          break;
        case 'forecast':
          aVal = a.client_forecast?.score || (a.rankability_score * 100) || 0;
          bVal = b.client_forecast?.score || (b.rankability_score * 100) || 0;
          break;
        case 'action':
          const actionOrder = { 'approved': 1, 'whole': 2, 'none': 3 };
          aVal = actionOrder[a.action_status] || 3;
          bVal = actionOrder[b.action_status] || 3;
          break;
        default:
          aVal = 0;
          bVal = 0;
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  };

  const filteredKeywords = getFilteredKeywords();
  const sortedKeywords = getSortedKeywords();

  // Format volume number
  const formatVolume = (vol) => {
    if (!vol) return '-';
    if (vol >= 1000000) return (vol / 1000000).toFixed(1) + 'M';
    if (vol >= 1000) return (vol / 1000).toFixed(1) + 'K';
    return vol.toString();
  };

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Strategy Dashboard</h1>
        <button
          onClick={() => navigate('/outline')}
          disabled={selectedCount === 0}
          className="px-4 py-2 bg-[#223540] text-white rounded hover:bg-[#00a99d] disabled:opacity-50 disabled:cursor-not-allowed text-sm"
        >
          Outline Builder {selectedCount > 0 && `(${selectedCount})`}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
          <p className="text-red-800 text-sm">{error}</p>
          <button onClick={() => setError('')} className="text-red-600 text-xs underline mt-1">Dismiss</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Sidebar - Lists */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow p-3">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-semibold">Lists</h2>
              <button
                onClick={() => setShowCreateForm(true)}
                className="text-xs px-2 py-1 bg-[#223540] text-white rounded hover:bg-[#00a99d]"
              >
                + New
              </button>
            </div>

            {selectedList && (
              <div className="mb-3 space-y-1">
                <button
                  onClick={() => setShowAddKeywordsForm(true)}
                  className="w-full text-xs px-2 py-1.5 bg-green-500 text-white rounded hover:bg-green-600"
                >
                  + Add Keywords
                </button>
                <button
                  onClick={() => handleDeleteList(selectedList.id)}
                  disabled={deletingList}
                  className="w-full text-xs px-2 py-1.5 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
                >
                  {deletingList ? 'Deleting...' : 'Delete List'}
                </button>
              </div>
            )}

            {showAddKeywordsForm && selectedList && (
              <form onSubmit={handleAddKeywords} className="mb-3 space-y-2 p-2 bg-gray-50 rounded text-xs">
                <h3 className="font-medium">Add to {selectedList.name}</h3>
                <textarea
                  placeholder="Keywords (one per line)"
                  value={keywordsToAdd}
                  onChange={(e) => setKeywordsToAdd(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-xs"
                  rows={4}
                  required
                />
                <div className="flex gap-1">
                  <button type="submit" disabled={loading} className="flex-1 px-2 py-1 bg-green-500 text-white rounded text-xs">
                    {loading ? 'Adding...' : 'Add'}
                  </button>
                  <button type="button" onClick={() => { setShowAddKeywordsForm(false); setKeywordsToAdd(''); }} className="px-2 py-1 bg-gray-300 rounded text-xs">
                    Cancel
                  </button>
                </div>
              </form>
            )}

            {showCreateForm && (
              <form onSubmit={handleCreateList} className="mb-3 space-y-2 p-2 bg-gray-50 rounded text-xs">
                <input
                  type="text"
                  placeholder="List name"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-xs"
                  required
                />
                <input
                  type="url"
                  placeholder="Target domain URL"
                  value={newTargetDomain}
                  onChange={(e) => setNewTargetDomain(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-xs"
                  required
                />
                <textarea
                  placeholder="Keywords (one per line)"
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  className="w-full px-2 py-1 border rounded text-xs"
                  rows={4}
                  required
                />
                <div className="border-t pt-2 mt-2">
                  <p className="text-xs font-medium text-gray-600 mb-1">Client Profile (Optional)</p>
                  <select
                    value={clientVertical}
                    onChange={(e) => setClientVertical(e.target.value)}
                    className="w-full px-2 py-1 border rounded text-xs mb-1"
                  >
                    {VERTICALS.map(v => (
                      <option key={v.value} value={v.value}>{v.label}</option>
                    ))}
                  </select>
                  {clientVertical && (
                    <textarea
                      placeholder="Vertical keywords (one per line)"
                      value={clientVerticalKeywords}
                      onChange={(e) => setClientVerticalKeywords(e.target.value)}
                      className="w-full px-2 py-1 border rounded text-xs"
                      rows={2}
                    />
                  )}
                </div>
                <div className="flex gap-1">
                  <button type="submit" disabled={loading} className="flex-1 px-2 py-1 bg-[#223540] text-white rounded text-xs">
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
                    className="px-2 py-1 bg-gray-300 rounded text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            <div className="space-y-1">
              {lists.map(list => (
                <div key={list.id} className="flex items-center gap-1">
                  <button
                    onClick={() => loadList(list.id)}
                    className={`flex-1 text-left px-2 py-1.5 rounded text-xs ${
                      selectedList?.id === list.id
                        ? 'bg-[#223540] text-white'
                        : 'bg-gray-100 hover:bg-gray-200'
                    }`}
                  >
                    <div className="font-medium truncate">{list.name}</div>
                    <div className="text-xs opacity-75">{list.keyword_count} kw</div>
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content - Keywords Table */}
        <div className="lg:col-span-4">
          {selectedList ? (
            <div className="bg-white rounded-lg shadow">
              <div className="p-3 border-b">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedList.name}</h2>
                    <p className="text-xs text-gray-600">{selectedList.target_domain_url}</p>
                    {selectedList.client_profile ? (
                      <p className="text-xs text-blue-600">
                        {VERTICALS.find(v => v.value === selectedList.client_profile.vertical)?.label || selectedList.client_profile.vertical}
                        <button onClick={openEditSettings} className="ml-1 text-gray-500 hover:text-gray-700 underline">Edit</button>
                      </p>
                    ) : (
                      <button onClick={openEditSettings} className="text-xs text-blue-600 hover:text-blue-700">
                        + Add Client Profile
                      </button>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleFetchVolumes}
                      disabled={fetchingVolumes}
                      className="px-3 py-1.5 bg-purple-600 text-white rounded text-xs hover:bg-purple-700 disabled:opacity-50"
                    >
                      {fetchingVolumes ? 'Fetching...' : 'Get Volumes'}
                    </button>
                    <button
                      onClick={handleScoreKeywords}
                      disabled={scoring || selectedForScoring.size === 0}
                      className="px-3 py-1.5 bg-[#223540] text-white rounded text-xs hover:bg-[#00a99d] disabled:opacity-50"
                    >
                      {scoring ? 'Scoring...' : `Score${selectedForScoring.size > 0 ? ` (${selectedForScoring.size})` : ''}`}
                    </button>
                    <button
                      onClick={handleExport}
                      className="px-3 py-1.5 bg-gray-500 text-white rounded text-xs hover:bg-gray-600"
                    >
                      Export
                    </button>
                  </div>
                </div>

                {/* Edit Settings Modal */}
                {showEditSettings && (
                  <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded text-xs">
                    <h3 className="font-medium text-gray-800 mb-2">Client Profile Settings</h3>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Business Vertical</label>
                        <select
                          value={editVertical}
                          onChange={(e) => setEditVertical(e.target.value)}
                          className="w-full px-2 py-1 border rounded text-xs"
                        >
                          {VERTICALS.map(v => (
                            <option key={v.value} value={v.value}>{v.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Core Topics</label>
                        <textarea
                          value={editVerticalKeywords}
                          onChange={(e) => setEditVerticalKeywords(e.target.value)}
                          rows={2}
                          className="w-full px-2 py-1 border rounded text-xs"
                        />
                      </div>
                    </div>
                    <div className="flex gap-2 mt-2">
                      <button onClick={handleSaveListSettings} disabled={savingSettings} className="px-3 py-1 bg-blue-600 text-white rounded text-xs">
                        {savingSettings ? 'Saving...' : 'Save'}
                      </button>
                      <button onClick={() => setShowEditSettings(false)} className="px-3 py-1 bg-gray-300 rounded text-xs">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {/* Filter Controls */}
                <div className="flex flex-wrap gap-2 items-center text-xs">
                  <input
                    type="text"
                    placeholder="Search..."
                    value={filterSearch}
                    onChange={(e) => setFilterSearch(e.target.value)}
                    className="px-2 py-1 border rounded text-xs w-32"
                  />
                  <select
                    value={filterScored}
                    onChange={(e) => setFilterScored(e.target.value)}
                    className="px-2 py-1 border rounded text-xs"
                  >
                    <option value="all">All</option>
                    <option value="scored">Scored</option>
                    <option value="unscored">Unscored</option>
                  </select>
                  <select
                    value={filterTier}
                    onChange={(e) => setFilterTier(e.target.value)}
                    className="px-2 py-1 border rounded text-xs"
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
                        <option value="T1_GO_NOW">T1</option>
                        <option value="T2_STRATEGIC">T2</option>
                        <option value="T3_LONG_GAME">T3</option>
                        <option value="T4_NOT_WORTH_IT">T4</option>
                      </>
                    )}
                  </select>
                  <span className="text-gray-500">
                    {filteredKeywords.length} of {selectedList.keywords?.length || 0}
                  </span>
                  {selectedForScoring.size > 0 && (
                    <button onClick={clearScoringSelection} className="text-gray-500 hover:text-gray-700 underline">
                      Clear
                    </button>
                  )}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-2 py-2 text-left w-8">
                        <input
                          type="checkbox"
                          checked={filteredKeywords.length > 0 && filteredKeywords.every(k => selectedForScoring.has(k.id))}
                          onChange={(e) => e.target.checked ? selectAllForScoring() : clearScoringSelection()}
                          className="h-3 w-3"
                        />
                      </th>
                      <th
                        className="px-2 py-2 text-left font-medium text-gray-600 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('keyword')}
                      >
                        Keyword<SortIndicator column="keyword" />
                      </th>
                      <th
                        className="px-2 py-2 text-right font-medium text-gray-600 cursor-pointer hover:bg-gray-100 w-20"
                        onClick={() => handleSort('volume')}
                      >
                        Volume<SortIndicator column="volume" />
                      </th>
                      <th
                        className="px-2 py-2 text-center font-medium text-gray-600 cursor-pointer hover:bg-gray-100 w-20"
                        onClick={() => handleSort('tier')}
                      >
                        Tier<SortIndicator column="tier" />
                      </th>
                      <th
                        className="px-2 py-2 text-right font-medium text-gray-600 cursor-pointer hover:bg-gray-100 w-20"
                        onClick={() => handleSort('forecast')}
                      >
                        Forecast<SortIndicator column="forecast" />
                      </th>
                      <th
                        className="px-2 py-2 text-center font-medium text-gray-600 cursor-pointer hover:bg-gray-100 w-24"
                        onClick={() => handleSort('action')}
                      >
                        Action<SortIndicator column="action" />
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sortedKeywords.map(keyword => {
                      const tier = keyword.client_forecast?.tier || keyword.opportunity_tier;
                      const forecast = keyword.client_forecast?.score || (keyword.rankability_score * 100);

                      return (
                        <tr key={keyword.id} className={`hover:bg-gray-50 ${selectedForScoring.has(keyword.id) ? 'bg-blue-50' : ''}`}>
                          <td className="px-2 py-1.5">
                            <input
                              type="checkbox"
                              checked={selectedForScoring.has(keyword.id)}
                              onChange={() => toggleScoringSelection(keyword.id)}
                              className="h-3 w-3"
                            />
                          </td>
                          <td className="px-2 py-1.5 font-medium">{keyword.keyword}</td>
                          <td className="px-2 py-1.5 text-right text-gray-600">
                            {formatVolume(keyword.volume)}
                          </td>
                          <td className="px-2 py-1.5 text-center">
                            {isKeywordScored(keyword) ? (
                              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${getTierColor(tier)}`}>
                                {getTierDisplayName(tier)}
                              </span>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </td>
                          <td className="px-2 py-1.5 text-right">
                            {isKeywordScored(keyword) && forecast ? (
                              <span className="font-medium">{forecast.toFixed(0)}%</span>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </td>
                          <td className="px-2 py-1.5 text-center">
                            <select
                              value={keyword.action_status || 'none'}
                              onChange={(e) => handleActionChange(keyword.id, e.target.value)}
                              className={`px-1.5 py-0.5 rounded text-xs border ${getActionColor(keyword.action_status)}`}
                            >
                              <option value="none">-</option>
                              <option value="approved">Approved</option>
                              <option value="whole">Whole</option>
                              <option value="remove">Remove</option>
                            </select>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <p className="text-gray-500 text-sm">Select a keyword list or create a new one</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StrategyDashboard;
