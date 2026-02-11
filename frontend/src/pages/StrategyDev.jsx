import { useState, useEffect, useCallback } from 'react';
import { strategyDevAPI, strategyAPI } from '../services/api';
import TopicFunnel from '../components/TopicFunnel';

const JOURNEY_STAGES = [
  'Decision / Action',
  'Validation / Trust',
  'Narrowing / Evaluation',
  'Exploration / Consideration',
  'Trigger / Awareness'
];

const STAGE_COLORS = {
  'Decision / Action': 'bg-green-100 text-green-800',
  'Validation / Trust': 'bg-blue-100 text-blue-800',
  'Narrowing / Evaluation': 'bg-purple-100 text-purple-800',
  'Exploration / Consideration': 'bg-orange-100 text-orange-800',
  'Trigger / Awareness': 'bg-gray-100 text-gray-800'
};

export default function StrategyDev() {
  // Projects state
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectData, setProjectData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // New project form
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newDomain, setNewDomain] = useState('');
  const [newTopics, setNewTopics] = useState([{ name: '', keywords: '' }]);

  // Edit project form
  const [showEditProject, setShowEditProject] = useState(false);
  const [editProjectId, setEditProjectId] = useState(null);
  const [editProjectName, setEditProjectName] = useState('');
  const [editDomain, setEditDomain] = useState('');
  const [editTopics, setEditTopics] = useState([{ name: '', keywords: '' }]);

  // GSC state
  const [gscSites, setGscSites] = useState([]);
  const [showSiteSelect, setShowSiteSelect] = useState(false);
  const [siteSearch, setSiteSearch] = useState('');
  const [maxPosition, setMaxPosition] = useState(''); // Position filter for sync

  // Filters
  const [topicFilter, setTopicFilter] = useState('');
  const [stageFilter, setStageFilter] = useState('');

  // Selection
  const [selectedKeywords, setSelectedKeywords] = useState(new Set());

  // Sort
  const [sortField, setSortField] = useState('clicks');
  const [sortDir, setSortDir] = useState('desc');

  // Export modal
  const [showExportModal, setShowExportModal] = useState(false);
  const [existingLists, setExistingLists] = useState([]);
  const [exportListId, setExportListId] = useState('');
  const [exportNewListName, setExportNewListName] = useState('');
  const [exportTargetDomain, setExportTargetDomain] = useState('');

  // Funnel Visualization
  const [showFunnel, setShowFunnel] = useState(false);
  const [funnelTopic, setFunnelTopic] = useState('');
  const [funnelData, setFunnelData] = useState(null);
  const [loadingFunnel, setLoadingFunnel] = useState(false);
  const [generatingStage, setGeneratingStage] = useState(null);

  // Bulk actions
  const [fetchingVolumes, setFetchingVolumes] = useState(false);
  const [deletingKeywords, setDeletingKeywords] = useState(false);
  const [fetchingFunnelVolumes, setFetchingFunnelVolumes] = useState(null); // stage id

  // Load projects
  useEffect(() => {
    loadProjects();
  }, []);

  // Listen for GSC OAuth callback
  useEffect(() => {
    const handleMessage = async (event) => {
      if (event.data?.type === 'GSC_AUTH_SUCCESS') {
        // Reload projects to get fresh GSC status
        const freshProjects = await strategyDevAPI.getProjects();
        setProjects(freshProjects);

        // Update selectedProject with fresh data and auto-show site selection
        if (selectedProject) {
          const freshProject = freshProjects.find(p => p.id === selectedProject.id);
          if (freshProject) {
            setSelectedProject(freshProject);
            // Auto-trigger site selection if GSC is now connected
            if (freshProject.gsc_connected) {
              try {
                const sites = await strategyDevAPI.listGscSites(freshProject.id);
                setGscSites(sites);
                setShowSiteSelect(true);
              } catch (err) {
                console.error('Failed to auto-load GSC sites:', err);
              }
            }
          }
        }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [selectedProject]);

  const loadProjects = async () => {
    try {
      const data = await strategyDevAPI.getProjects();
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  };

  const loadProjectData = useCallback(async (showLoading = true) => {
    if (!selectedProject) return;
    if (showLoading) setLoading(true);
    try {
      const data = await strategyDevAPI.getProject(
        selectedProject.id,
        topicFilter || null,
        stageFilter || null
      );
      setProjectData(data);
      // Only clear selection on initial load, not refreshes
      if (showLoading) setSelectedKeywords(new Set());
    } catch (err) {
      console.error('Failed to load project:', err);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [selectedProject, topicFilter, stageFilter]);

  useEffect(() => {
    loadProjectData();
  }, [loadProjectData]);

  // Resume polling if project is already syncing
  useEffect(() => {
    if (selectedProject?.sync_status === 'syncing' && !syncing) {
      setSyncing(true);
      pollSyncStatus();
    }
  }, [selectedProject?.id]);

  const loadGscSites = async () => {
    if (!selectedProject?.id) return;
    try {
      const sites = await strategyDevAPI.listGscSites(selectedProject.id);
      setGscSites(sites);
      setShowSiteSelect(true);
    } catch (err) {
      console.error('Failed to load GSC sites:', err);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;

    const topics = newTopics
      .filter(t => t.name.trim())
      .map(t => ({
        name: t.name.trim(),
        keywords: t.keywords.split(',').map(k => k.trim()).filter(k => k)
      }));

    try {
      const project = await strategyDevAPI.createProject(newProjectName, newDomain || null, topics.length ? topics : null);
      setProjects([project, ...projects]);
      setSelectedProject(project);
      setShowNewProject(false);
      setNewProjectName('');
      setNewDomain('');
      setNewTopics([{ name: '', keywords: '' }]);
    } catch (err) {
      console.error('Failed to create project:', err);
      alert('Failed to create project');
    }
  };

  const handleConnectGsc = async () => {
    if (!selectedProject) return;
    try {
      const { auth_url, configured } = await strategyDevAPI.getGscAuthUrl(selectedProject.id);
      if (!configured) {
        alert('Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.');
        return;
      }
      // Open OAuth popup
      window.open(auth_url, 'GSC Auth', 'width=600,height=700');
    } catch (err) {
      console.error('Failed to get auth URL:', err);
      alert('Failed to connect to Google');
    }
  };

  const handleSelectSite = async (siteUrl) => {
    if (!selectedProject) return;
    try {
      await strategyDevAPI.updateProject(selectedProject.id, { gsc_property_url: siteUrl });
      setSelectedProject({ ...selectedProject, gsc_property_url: siteUrl });
      setShowSiteSelect(false);
      loadProjects();
    } catch (err) {
      console.error('Failed to select site:', err);
    }
  };

  const handleSync = async () => {
    if (!selectedProject) return;
    setSyncing(true);
    try {
      const posFilter = maxPosition ? parseFloat(maxPosition) : null;
      await strategyDevAPI.syncProject(selectedProject.id, posFilter);
      // Start polling for sync status
      pollSyncStatus();
    } catch (err) {
      console.error('Sync failed:', err);
      alert('Sync failed: ' + (err.response?.data?.detail || err.message));
      setSyncing(false);
    }
  };

  // Poll for sync status
  const pollSyncStatus = useCallback(async () => {
    if (!selectedProject) return;

    const checkStatus = async () => {
      try {
        const data = await strategyDevAPI.getProject(selectedProject.id);
        const status = data.project.sync_status;
        const message = data.project.sync_message;

        // Update selected project with latest status message
        setSelectedProject(prev => ({
          ...prev,
          sync_status: status,
          sync_message: message
        }));

        if (status === 'syncing') {
          // Continue polling - don't update table data mid-sync
          setTimeout(checkStatus, 3000);
        } else {
          // Sync complete or error - NOW refresh table data
          setProjectData(data);
          setSyncing(false);
          loadProjects();

          if (status === 'error') {
            alert('Sync failed: ' + (message || 'Unknown error'));
          }
        }
      } catch (err) {
        console.error('Failed to check sync status:', err);
        setSyncing(false);
      }
    };

    // Start polling
    setTimeout(checkStatus, 1000);
  }, [selectedProject]);

  const handleDeleteProject = async (projectId) => {
    if (!confirm('Delete this project and all its keywords?')) return;
    try {
      await strategyDevAPI.deleteProject(projectId);
      setProjects(projects.filter(p => p.id !== projectId));
      if (selectedProject?.id === projectId) {
        setSelectedProject(null);
        setProjectData(null);
      }
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  };

  const openEditProject = (project) => {
    setEditProjectId(project.id);
    setEditProjectName(project.name);
    setEditDomain(project.domain || '');
    // Convert core_topics to editable format
    if (project.core_topics && project.core_topics.length > 0) {
      setEditTopics(project.core_topics.map(t => ({
        name: t.name || '',
        keywords: (t.keywords || []).join(', ')
      })));
    } else {
      setEditTopics([{ name: '', keywords: '' }]);
    }
    setShowEditProject(true);
  };

  const handleEditProject = async (e) => {
    e.preventDefault();
    if (!editProjectName.trim()) return;

    const topics = editTopics
      .filter(t => t.name.trim())
      .map(t => ({
        name: t.name.trim(),
        keywords: t.keywords.split(',').map(k => k.trim()).filter(k => k)
      }));

    try {
      const updated = await strategyDevAPI.updateProject(editProjectId, {
        name: editProjectName,
        domain: editDomain || null,
        core_topics: topics.length ? topics : null
      });
      // Update projects list
      setProjects(projects.map(p => p.id === editProjectId ? { ...p, ...updated } : p));
      // Update selected project if it's the one being edited
      if (selectedProject?.id === editProjectId) {
        setSelectedProject({ ...selectedProject, ...updated });
      }
      setShowEditProject(false);
      loadProjects(); // Refresh to get latest data
    } catch (err) {
      console.error('Failed to update project:', err);
      alert('Failed to update project');
    }
  };

  // Sorting
  const sortedKeywords = (projectData?.keywords || []).sort((a, b) => {
    let aVal = a[sortField];
    let bVal = b[sortField];
    if (typeof aVal === 'string') aVal = aVal?.toLowerCase() || '';
    if (typeof bVal === 'string') bVal = bVal?.toLowerCase() || '';
    if (aVal === null || aVal === undefined) aVal = sortDir === 'asc' ? Infinity : -Infinity;
    if (bVal === null || bVal === undefined) bVal = sortDir === 'asc' ? Infinity : -Infinity;
    if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  // Selection
  const toggleSelectAll = () => {
    if (selectedKeywords.size === sortedKeywords.length) {
      setSelectedKeywords(new Set());
    } else {
      setSelectedKeywords(new Set(sortedKeywords.map(k => k.id)));
    }
  };

  const toggleSelect = (id) => {
    const next = new Set(selectedKeywords);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedKeywords(next);
  };

  // Export
  const handleExportCsv = async () => {
    if (selectedKeywords.size === 0) {
      alert('Select keywords to export');
      return;
    }
    try {
      const blob = await strategyDevAPI.exportKeywordsCsv([...selectedKeywords]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'keywords_export.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed');
    }
  };

  const openExportToListModal = async () => {
    if (selectedKeywords.size === 0) {
      alert('Select keywords to export');
      return;
    }
    try {
      const lists = await strategyAPI.getLists();
      setExistingLists(lists);
      setShowExportModal(true);
    } catch (err) {
      console.error('Failed to load lists:', err);
    }
  };

  const handleExportToList = async () => {
    try {
      let result;
      if (exportListId) {
        result = await strategyDevAPI.addKeywordsToList([...selectedKeywords], parseInt(exportListId));
      } else if (exportNewListName && exportTargetDomain) {
        result = await strategyDevAPI.addKeywordsToList(
          [...selectedKeywords],
          null,
          exportNewListName,
          exportTargetDomain
        );
      } else {
        alert('Select an existing list or enter new list details');
        return;
      }
      alert(result.message);
      setShowExportModal(false);
      setExportListId('');
      setExportNewListName('');
      setExportTargetDomain('');
    } catch (err) {
      console.error('Export failed:', err);
      alert('Failed to add to list');
    }
  };

  // Delete selected keywords
  const handleDeleteSelected = async () => {
    if (selectedKeywords.size === 0) {
      alert('Select keywords to delete');
      return;
    }
    if (!confirm(`Delete ${selectedKeywords.size} selected keywords?`)) return;

    setDeletingKeywords(true);
    try {
      const result = await strategyDevAPI.deleteKeywordsBulk([...selectedKeywords]);
      alert(result.message);
      setSelectedKeywords(new Set());
      loadProjectData(false); // Refresh without flash
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Failed to delete keywords');
    } finally {
      setDeletingKeywords(false);
    }
  };

  // Fetch volumes for selected keywords (or all if none selected)
  const handleFetchVolumes = async () => {
    if (!selectedProject) return;

    setFetchingVolumes(true);
    try {
      const keywordIds = selectedKeywords.size > 0 ? [...selectedKeywords] : null;
      const result = await strategyDevAPI.fetchStrategyVolumes(selectedProject.id, keywordIds);
      alert(result.message);
      loadProjectData(false); // Refresh without flash
    } catch (err) {
      console.error('Fetch volumes failed:', err);
      alert('Failed to fetch volumes: ' + (err.response?.data?.detail || err.message));
    } finally {
      setFetchingVolumes(false);
    }
  };

  // Get unique topics from keywords
  const uniqueTopics = [...new Set((projectData?.keywords || []).map(k => k.assigned_topic).filter(Boolean))];

  // Load funnel visualization
  const handleVisualizeTopic = async (topic) => {
    if (!selectedProject) return;
    setFunnelTopic(topic);
    setLoadingFunnel(true);
    setShowFunnel(true);
    try {
      const data = await strategyDevAPI.getFunnelData(selectedProject.id, topic);
      setFunnelData(data);
    } catch (err) {
      console.error('Failed to load funnel:', err);
      setFunnelData(null);
    } finally {
      setLoadingFunnel(false);
    }
  };

  // Reload funnel data
  const reloadFunnelData = async () => {
    if (!selectedProject || !funnelTopic) return;
    try {
      const data = await strategyDevAPI.getFunnelData(selectedProject.id, funnelTopic);
      setFunnelData(data);
    } catch (err) {
      console.error('Failed to reload funnel:', err);
    }
  };

  // Move keyword to different stage
  const handleMoveKeyword = async (keywordId, newStage) => {
    try {
      await strategyDevAPI.updateKeywordStage(keywordId, newStage);
      reloadFunnelData();
    } catch (err) {
      console.error('Failed to move keyword:', err);
      alert('Failed to move keyword');
    }
  };

  // Delete keyword
  const handleDeleteFunnelKeyword = async (keywordId) => {
    if (!confirm('Delete this keyword?')) return;
    try {
      await strategyDevAPI.deleteStrategyKeyword(keywordId);
      reloadFunnelData();
      loadProjectData(); // Refresh main table too
    } catch (err) {
      console.error('Failed to delete keyword:', err);
      alert('Failed to delete keyword');
    }
  };

  // Generate queries for a stage
  const handleGenerateQueries = async (stage) => {
    if (!selectedProject || !funnelTopic) return;
    setGeneratingStage(stage);
    try {
      const result = await strategyDevAPI.generateQueries(selectedProject.id, stage, funnelTopic);
      alert(`Generated ${result.keywords.length} new queries`);
      reloadFunnelData();
      loadProjectData(false);
    } catch (err) {
      console.error('Failed to generate queries:', err);
      alert('Failed to generate queries: ' + (err.response?.data?.detail || err.message));
    } finally {
      setGeneratingStage(null);
    }
  };

  // Fetch volumes for a funnel stage
  const handleFetchFunnelVolumes = async (stage) => {
    if (!selectedProject || !funnelData) return;

    // Get keyword IDs for this stage
    const stageData = funnelData.stages[stage];
    if (!stageData || stageData.keywords.length === 0) {
      alert('No keywords in this stage');
      return;
    }

    const keywordIds = stageData.keywords.map(kw => kw.id);
    setFetchingFunnelVolumes(stage);

    try {
      const result = await strategyDevAPI.fetchStrategyVolumes(selectedProject.id, keywordIds);
      alert(result.message);
      reloadFunnelData();
      loadProjectData(false);
    } catch (err) {
      console.error('Fetch volumes failed:', err);
      alert('Failed to fetch volumes: ' + (err.response?.data?.detail || err.message));
    } finally {
      setFetchingFunnelVolumes(null);
    }
  };

  // Export funnel as CSV
  const handleExportFunnelCsv = async () => {
    if (!selectedProject) return;
    try {
      const blob = await strategyDevAPI.exportFunnelCsv(selectedProject.id, funnelTopic);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `funnel_${funnelTopic || 'all'}.csv`.replace(/ /g, '_');
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed');
    }
  };

  // Export funnel as PDF
  const handleExportFunnelPdf = async () => {
    if (!selectedProject) return;
    try {
      const blob = await strategyDevAPI.exportFunnelPdf(selectedProject.id, funnelTopic);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `funnel_report_${funnelTopic || 'all'}.pdf`.replace(/ /g, '_');
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed:', err);
      alert('PDF export failed');
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r overflow-y-auto">
        <div className="p-4 border-b">
          <button
            onClick={() => setShowNewProject(true)}
            className="w-full bg-[#223540] text-white py-2 px-4 rounded hover:bg-[#2d4654] text-sm"
          >
            + New Project
          </button>
        </div>

        <div className="p-2">
          {projects.map(p => (
            <div
              key={p.id}
              className={`p-3 rounded cursor-pointer mb-1 ${
                selectedProject?.id === p.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50'
              }`}
              onClick={() => setSelectedProject(p)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{p.name}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {p.keyword_count} keywords
                    {p.gsc_connected && <span className="ml-2 text-green-600">GSC Connected</span>}
                    {p.sync_status === 'syncing' && (
                      <span className="ml-2 text-blue-600 animate-pulse">Syncing...</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); openEditProject(p); }}
                    className="text-gray-400 hover:text-blue-500 p-1 text-xs"
                    title="Edit project"
                  >
                    Edit
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteProject(p.id); }}
                    className="text-gray-400 hover:text-red-500 p-1"
                    title="Delete project"
                  >
                    ×
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto bg-gray-50">
        {!selectedProject ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Select a project or create a new one
          </div>
        ) : (
          <div className="p-6">
            {/* Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-gray-900">{selectedProject.name}</h1>
              <div className="mt-2 flex items-center gap-4">
                {!selectedProject.gsc_connected ? (
                  <button
                    onClick={handleConnectGsc}
                    className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
                  >
                    Connect Google Search Console
                  </button>
                ) : (
                  <>
                    <span className="text-sm text-green-600">
                      GSC: {selectedProject.gsc_property_url || 'Connected'}
                    </span>
                    {!selectedProject.gsc_property_url && (
                      <button
                        onClick={loadGscSites}
                        className="bg-gray-100 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-200"
                      >
                        Select Site
                      </button>
                    )}
                    {selectedProject.gsc_property_url && (
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1">
                          <label className="text-xs text-gray-600">Max Position:</label>
                          <input
                            type="number"
                            value={maxPosition}
                            onChange={(e) => setMaxPosition(e.target.value)}
                            placeholder="e.g. 20"
                            className="w-20 border rounded px-2 py-1 text-sm"
                            min="1"
                            max="100"
                            disabled={syncing}
                          />
                        </div>
                        <button
                          onClick={handleSync}
                          disabled={syncing}
                          className="bg-[#223540] text-white px-4 py-2 rounded text-sm hover:bg-[#2d4654] disabled:opacity-50"
                        >
                          {syncing ? 'Syncing...' : 'Sync Data'}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Sync Status */}
              {syncing && (
                <div className="mt-3 flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4 text-blue-600" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  <span className="text-sm text-blue-600">
                    {selectedProject.sync_message || 'Starting sync...'}
                  </span>
                </div>
              )}
              {!syncing && selectedProject?.sync_status === 'complete' && selectedProject.sync_message && (
                <div className="mt-2">
                  <span className="text-sm text-green-600">
                    {selectedProject.sync_message}
                  </span>
                </div>
              )}
            </div>

            {/* Core Topics Display */}
            {selectedProject.core_topics?.length > 0 && (
              <div className="mb-4 bg-white rounded-lg p-4 shadow-sm">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Core Topics</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedProject.core_topics.map((t, i) => (
                    <div key={i} className="flex items-center gap-1">
                      <span className="bg-gray-100 text-gray-700 px-3 py-1 rounded-full text-sm">
                        {t.name}
                      </span>
                      {(projectData?.keywords?.length > 0) && (
                        <button
                          onClick={() => handleVisualizeTopic(t.name)}
                          className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200"
                          title="View buyer journey funnel"
                        >
                          Funnel
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Filters */}
            <div className="mb-4 flex gap-4 items-center">
              <select
                value={topicFilter}
                onChange={(e) => setTopicFilter(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="">All Topics</option>
                {uniqueTopics.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <select
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="">All Stages</option>
                {JOURNEY_STAGES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              {/* Fetch Volumes Button (always visible) */}
              <button
                onClick={handleFetchVolumes}
                disabled={fetchingVolumes}
                className="bg-purple-100 text-purple-700 px-3 py-2 rounded text-sm hover:bg-purple-200 disabled:opacity-50"
              >
                {fetchingVolumes ? 'Fetching...' : (selectedKeywords.size > 0 ? `Fetch Volumes (${selectedKeywords.size})` : 'Fetch All Volumes')}
              </button>

              <div className="flex-1" />

              {/* Actions for selected keywords */}
              {selectedKeywords.size > 0 && (
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteSelected}
                    disabled={deletingKeywords}
                    className="bg-red-100 text-red-700 px-3 py-2 rounded text-sm hover:bg-red-200 disabled:opacity-50"
                  >
                    {deletingKeywords ? 'Deleting...' : `Delete (${selectedKeywords.size})`}
                  </button>
                  <button
                    onClick={handleExportCsv}
                    className="bg-gray-100 text-gray-700 px-3 py-2 rounded text-sm hover:bg-gray-200"
                  >
                    Export CSV ({selectedKeywords.size})
                  </button>
                  <button
                    onClick={openExportToListModal}
                    className="bg-[#223540] text-white px-3 py-2 rounded text-sm hover:bg-[#2d4654]"
                  >
                    Add to Rank Predict
                  </button>
                </div>
              )}
            </div>

            {/* Keywords Table */}
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading...</div>
            ) : (
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="w-10 px-3 py-3">
                        <input
                          type="checkbox"
                          checked={selectedKeywords.size === sortedKeywords.length && sortedKeywords.length > 0}
                          onChange={toggleSelectAll}
                          className="rounded"
                        />
                      </th>
                      <th
                        className="text-left px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('query')}
                      >
                        Query <SortIcon field="query" />
                      </th>
                      <th className="text-left px-3 py-3">
                        Page URL
                      </th>
                      <th
                        className="text-left px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('assigned_topic')}
                      >
                        Topic <SortIcon field="assigned_topic" />
                      </th>
                      <th
                        className="text-left px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('buyer_journey_stage')}
                      >
                        Journey Stage <SortIcon field="buyer_journey_stage" />
                      </th>
                      <th
                        className="text-right px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('clicks')}
                      >
                        Clicks <SortIcon field="clicks" />
                      </th>
                      <th
                        className="text-right px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('impressions')}
                      >
                        Impressions <SortIcon field="impressions" />
                      </th>
                      <th
                        className="text-right px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('avg_position')}
                      >
                        Avg Pos <SortIcon field="avg_position" />
                      </th>
                      <th
                        className="text-right px-3 py-3 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('volume')}
                      >
                        Volume <SortIcon field="volume" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedKeywords.map(kw => (
                      <tr key={kw.id} className="border-b hover:bg-gray-50">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selectedKeywords.has(kw.id)}
                            onChange={() => toggleSelect(kw.id)}
                            className="rounded"
                          />
                        </td>
                        <td className="px-3 py-2 font-medium">{kw.query}</td>
                        <td className="px-3 py-2">
                          {kw.page_url ? (
                            <a
                              href={kw.page_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline text-xs truncate block max-w-[200px]"
                              title={kw.page_url}
                            >
                              {kw.page_url.replace(/^https?:\/\//, '').slice(0, 35)}...
                            </a>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {kw.assigned_topic && (
                            <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {kw.assigned_topic}
                              {kw.topic_similarity && (
                                <span className="ml-1 text-gray-400">
                                  ({Math.round(kw.topic_similarity * 100)}%)
                                </span>
                              )}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {kw.buyer_journey_stage && (
                            <span className={`text-xs px-2 py-1 rounded ${STAGE_COLORS[kw.buyer_journey_stage] || 'bg-gray-100'}`}>
                              {kw.buyer_journey_stage}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">{kw.clicks?.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right">{kw.impressions?.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right">
                          {kw.avg_position ? kw.avg_position.toFixed(1) : '-'}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {kw.volume ? kw.volume.toLocaleString() : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {sortedKeywords.length === 0 && (
                  <div className="text-center py-8 text-gray-500">
                    No keywords found. {selectedProject.gsc_property_url ? 'Click "Sync Data" to fetch keywords.' : 'Connect and select a GSC property first.'}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* New Project Modal */}
      {showNewProject && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4">Create New Project</h2>
            <form onSubmit={handleCreateProject}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Project Name
                </label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  placeholder="e.g., Client Site Analysis"
                  required
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Domain
                </label>
                <input
                  type="text"
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  placeholder="e.g., example.com"
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Core Topics (Optional)
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Define topics to classify keywords. Add example keywords for each topic.
                </p>
                {newTopics.map((topic, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={topic.name}
                      onChange={(e) => {
                        const next = [...newTopics];
                        next[i].name = e.target.value;
                        setNewTopics(next);
                      }}
                      className="flex-1 border rounded px-3 py-2 text-sm"
                      placeholder="Topic name"
                    />
                    <input
                      type="text"
                      value={topic.keywords}
                      onChange={(e) => {
                        const next = [...newTopics];
                        next[i].keywords = e.target.value;
                        setNewTopics(next);
                      }}
                      className="flex-1 border rounded px-3 py-2 text-sm"
                      placeholder="Example keywords (comma-separated)"
                    />
                    {newTopics.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setNewTopics(newTopics.filter((_, j) => j !== i))}
                        className="text-red-500 px-2"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setNewTopics([...newTopics, { name: '', keywords: '' }])}
                  className="text-sm text-blue-600 hover:underline"
                >
                  + Add Topic
                </button>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowNewProject(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#223540] text-white rounded hover:bg-[#2d4654]"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Project Modal */}
      {showEditProject && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4">Edit Project</h2>
            <form onSubmit={handleEditProject}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Project Name
                </label>
                <input
                  type="text"
                  value={editProjectName}
                  onChange={(e) => setEditProjectName(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  required
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Domain
                </label>
                <input
                  type="text"
                  value={editDomain}
                  onChange={(e) => setEditDomain(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  placeholder="e.g., example.com"
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Core Topics
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Define topics to classify keywords. Add example keywords for each topic.
                </p>
                {editTopics.map((topic, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={topic.name}
                      onChange={(e) => {
                        const next = [...editTopics];
                        next[i].name = e.target.value;
                        setEditTopics(next);
                      }}
                      className="flex-1 border rounded px-3 py-2 text-sm"
                      placeholder="Topic name"
                    />
                    <input
                      type="text"
                      value={topic.keywords}
                      onChange={(e) => {
                        const next = [...editTopics];
                        next[i].keywords = e.target.value;
                        setEditTopics(next);
                      }}
                      className="flex-1 border rounded px-3 py-2 text-sm"
                      placeholder="Example keywords (comma-separated)"
                    />
                    {editTopics.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setEditTopics(editTopics.filter((_, j) => j !== i))}
                        className="text-red-500 px-2"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setEditTopics([...editTopics, { name: '', keywords: '' }])}
                  className="text-sm text-blue-600 hover:underline"
                >
                  + Add Topic
                </button>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowEditProject(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#223540] text-white rounded hover:bg-[#2d4654]"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Site Select Modal */}
      {showSiteSelect && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md p-6">
            <h2 className="text-lg font-bold mb-4">Select GSC Property</h2>
            {gscSites.length === 0 ? (
              <p className="text-gray-500">No sites found. Make sure your Google account has access to Search Console properties.</p>
            ) : (
              <>
                <input
                  type="text"
                  value={siteSearch}
                  onChange={(e) => setSiteSearch(e.target.value)}
                  className="w-full border rounded px-3 py-2 mb-3 text-sm"
                  placeholder="Search sites..."
                  autoFocus
                />
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {gscSites
                    .filter(site => site.site_url.toLowerCase().includes(siteSearch.toLowerCase()))
                    .map((site, i) => (
                      <button
                        key={i}
                        onClick={() => { handleSelectSite(site.site_url); setSiteSearch(''); }}
                        className="w-full text-left p-3 border rounded hover:bg-gray-50"
                      >
                        <div className="font-medium text-sm">{site.site_url}</div>
                        <div className="text-xs text-gray-500">{site.permission_level}</div>
                      </button>
                    ))}
                  {gscSites.filter(site => site.site_url.toLowerCase().includes(siteSearch.toLowerCase())).length === 0 && (
                    <p className="text-sm text-gray-500 text-center py-2">No matching sites</p>
                  )}
                </div>
              </>
            )}
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => { setShowSiteSelect(false); setSiteSearch(''); }}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export to List Modal */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md p-6">
            <h2 className="text-lg font-bold mb-4">Add to Rank Predict List</h2>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select Existing List
              </label>
              <select
                value={exportListId}
                onChange={(e) => { setExportListId(e.target.value); setExportNewListName(''); }}
                className="w-full border rounded px-3 py-2"
              >
                <option value="">-- Select a list --</option>
                {existingLists.map(list => (
                  <option key={list.id} value={list.id}>{list.name}</option>
                ))}
              </select>
            </div>

            <div className="text-center text-gray-400 text-sm my-4">OR</div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Create New List
              </label>
              <input
                type="text"
                value={exportNewListName}
                onChange={(e) => { setExportNewListName(e.target.value); setExportListId(''); }}
                className="w-full border rounded px-3 py-2 mb-2"
                placeholder="New list name"
              />
              {exportNewListName && (
                <input
                  type="text"
                  value={exportTargetDomain}
                  onChange={(e) => setExportTargetDomain(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  placeholder="Target domain URL"
                  required
                />
              )}
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowExportModal(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleExportToList}
                className="px-4 py-2 bg-[#223540] text-white rounded hover:bg-[#2d4654]"
              >
                Add Keywords
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Topic Funnel Modal */}
      {showFunnel && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-6xl h-[90vh] p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-lg font-bold">
                  Buyer Journey Funnel: {funnelTopic}
                </h2>
                <p className="text-sm text-gray-500">
                  Click stages to expand. Move keywords between stages or generate new queries.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleExportFunnelCsv}
                  className="bg-gray-100 text-gray-700 px-3 py-1.5 rounded text-sm hover:bg-gray-200"
                >
                  Export CSV
                </button>
                <button
                  onClick={handleExportFunnelPdf}
                  className="bg-[#223540] text-white px-3 py-1.5 rounded text-sm hover:bg-[#2d4654]"
                >
                  Export PDF
                </button>
                <button
                  onClick={() => setShowFunnel(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl ml-4"
                >
                  ×
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              <TopicFunnel
                funnelData={funnelData}
                onMoveKeyword={handleMoveKeyword}
                onDeleteKeyword={handleDeleteFunnelKeyword}
                onGenerateQueries={handleGenerateQueries}
                onFetchVolumes={handleFetchFunnelVolumes}
                generatingStage={generatingStage}
                fetchingVolumes={fetchingFunnelVolumes}
                loading={loadingFunnel}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
