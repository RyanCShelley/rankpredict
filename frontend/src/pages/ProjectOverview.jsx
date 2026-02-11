import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { strategyDevAPI } from '../services/api';

export default function ProjectOverview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Persona modal
  const [showPersona, setShowPersona] = useState(false);
  const [personaDesc, setPersonaDesc] = useState('');
  const [personaExpanded, setPersonaExpanded] = useState('');
  const [personaGenerating, setPersonaGenerating] = useState(false);
  const [personaSaving, setPersonaSaving] = useState(false);

  // Edit modal
  const [showEdit, setShowEdit] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDomain, setEditDomain] = useState('');
  const [editTopics, setEditTopics] = useState([{ name: '', keywords: '' }]);

  useEffect(() => {
    loadProject();
  }, [id]);

  const loadProject = async () => {
    try {
      const [projectData, statsData] = await Promise.all([
        strategyDevAPI.getProject(id),
        strategyDevAPI.getProjectStats(id)
      ]);
      setProject(projectData.project);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load project:', err);
    } finally {
      setLoading(false);
    }
  };

  const openEdit = () => {
    if (!project) return;
    setEditName(project.name);
    setEditDomain(project.domain || '');
    if (project.core_topics?.length > 0) {
      setEditTopics(project.core_topics.map(t => ({
        name: t.name || '',
        keywords: (t.keywords || []).join(', ')
      })));
    } else {
      setEditTopics([{ name: '', keywords: '' }]);
    }
    setShowEdit(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    const topics = editTopics
      .filter(t => t.name.trim())
      .map(t => ({
        name: t.name.trim(),
        keywords: t.keywords.split(',').map(k => k.trim()).filter(k => k)
      }));

    try {
      const updated = await strategyDevAPI.updateProject(id, {
        name: editName,
        domain: editDomain || null,
        core_topics: topics.length ? topics : null
      });
      setProject({ ...project, ...updated });
      setShowEdit(false);
      loadProject();
    } catch (err) {
      console.error('Failed to update project:', err);
      alert('Failed to update project');
    }
  };

  const handleConnectGsc = async () => {
    try {
      const { auth_url, configured } = await strategyDevAPI.getGscAuthUrl(id);
      if (!configured) {
        alert('Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.');
        return;
      }
      window.open(auth_url, 'GSC Auth', 'width=600,height=700');
    } catch (err) {
      console.error('Failed to get auth URL:', err);
      alert('Failed to connect to Google');
    }
  };

  const openPersonaModal = () => {
    setPersonaDesc(project?.persona?.description || '');
    setPersonaExpanded(project?.persona?.expanded || '');
    setShowPersona(true);
  };

  const handleGeneratePersona = async () => {
    if (!personaDesc.trim()) return;
    setPersonaGenerating(true);
    try {
      const { persona } = await strategyDevAPI.generatePersona(id, personaDesc.trim());
      setPersonaExpanded(persona.expanded);
    } catch (err) {
      console.error('Failed to generate persona:', err);
      alert('Failed to generate persona');
    } finally {
      setPersonaGenerating(false);
    }
  };

  const handleSavePersona = async () => {
    setPersonaSaving(true);
    try {
      const persona = personaDesc.trim()
        ? { description: personaDesc.trim(), expanded: personaExpanded }
        : null;
      await strategyDevAPI.updateProject(id, { persona });
      setProject({ ...project, persona });
      setShowPersona(false);
    } catch (err) {
      console.error('Failed to save persona:', err);
      alert('Failed to save persona');
    } finally {
      setPersonaSaving(false);
    }
  };

  // Listen for GSC callback
  useEffect(() => {
    const handleMessage = (event) => {
      if (event.data?.type === 'GSC_AUTH_SUCCESS') {
        loadProject();
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading project...</div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-gray-500">Project not found.</p>
        <Link to="/" className="text-blue-600 hover:underline mt-2 inline-block">Back to Projects</Link>
      </div>
    );
  }

  const navCards = [
    {
      title: 'Strategy Dev',
      description: 'GSC data, topic funnels, buyer journey analysis',
      path: '/strategy-dev',
      color: 'bg-blue-50 border-blue-200 hover:border-blue-400',
      icon: (
        <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      )
    },
    {
      title: 'Rank Predict',
      description: 'Keyword scoring, rankability analysis, forecasting',
      path: '/predict',
      color: 'bg-purple-50 border-purple-200 hover:border-purple-400',
      icon: (
        <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      )
    },
    {
      title: 'Outline Builder',
      description: 'Content briefs, SERP analysis, outline generation',
      path: '/outline',
      color: 'bg-green-50 border-green-200 hover:border-green-400',
      icon: (
        <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      )
    }
  ];

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Back link */}
      <Link to="/" className="text-sm text-gray-500 hover:text-gray-700 mb-6 inline-flex items-center gap-1">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Projects
      </Link>

      {/* Header */}
      <div className="flex justify-between items-start mb-8 mt-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          {project.domain && (
            <p className="text-gray-500 mt-1">{project.domain}</p>
          )}
          <div className="flex items-center gap-3 mt-2">
            {project.gsc_connected ? (
              <span className="text-sm bg-green-100 text-green-700 px-3 py-1 rounded-full">
                GSC Connected
                {project.gsc_property_url && ` - ${project.gsc_property_url}`}
              </span>
            ) : (
              <button
                onClick={handleConnectGsc}
                className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700"
              >
                Connect Google Search Console
              </button>
            )}
          </div>
        </div>
        <button
          onClick={openEdit}
          className="text-sm bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200"
        >
          Edit Project
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-3xl font-bold text-[#223540]">{stats?.num_funnels || 0}</div>
          <div className="text-sm text-gray-500 mt-1">Funnels</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-3xl font-bold text-[#223540]">{stats?.num_terms || 0}</div>
          <div className="text-sm text-gray-500 mt-1">Terms</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-3xl font-bold text-[#223540]">{stats?.num_briefs || 0}</div>
          <div className="text-sm text-gray-500 mt-1">Briefs</div>
        </div>
      </div>

      {/* Persona section */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-8">
        <div className="flex justify-between items-start mb-2">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Persona</h2>
          {project.persona ? (
            <div className="flex gap-2">
              <button
                onClick={openPersonaModal}
                className="text-xs text-blue-600 hover:underline"
              >
                Edit
              </button>
            </div>
          ) : null}
        </div>
        {project.persona?.expanded ? (
          <div>
            <p className="text-xs text-gray-500 mb-1">{project.persona.description}</p>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{project.persona.expanded}</p>
          </div>
        ) : (
          <button
            onClick={openPersonaModal}
            className="text-sm bg-[#223540] text-white px-4 py-2 rounded-lg hover:bg-[#2d4654]"
          >
            Add Persona
          </button>
        )}
      </div>

      {/* Nav cards */}
      <div className="grid grid-cols-3 gap-6">
        {navCards.map(card => (
          <Link
            key={card.title}
            to={card.path}
            className={`rounded-lg border-2 p-6 transition-all ${card.color}`}
          >
            <div className="mb-3">{card.icon}</div>
            <h3 className="font-semibold text-gray-900 mb-1">{card.title}</h3>
            <p className="text-sm text-gray-600">{card.description}</p>
          </Link>
        ))}
      </div>

      {/* Persona Modal */}
      {showPersona && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-4">
              {project.persona ? 'Edit Persona' : 'Add Persona'}
            </h2>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Brief Description
              </label>
              <textarea
                value={personaDesc}
                onChange={(e) => setPersonaDesc(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
                rows={3}
                placeholder="e.g., RV owners looking for comfortable custom-fit mattresses"
              />
            </div>

            <button
              onClick={handleGeneratePersona}
              disabled={personaGenerating || !personaDesc.trim()}
              className="mb-4 text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {personaGenerating ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating...
                </>
              ) : (
                'Generate with AI'
              )}
            </button>

            {personaExpanded && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expanded Persona
                </label>
                <textarea
                  value={personaExpanded}
                  onChange={(e) => setPersonaExpanded(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm"
                  rows={8}
                />
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowPersona(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleSavePersona}
                disabled={personaSaving}
                className="px-4 py-2 bg-[#223540] text-white rounded hover:bg-[#2d4654] disabled:opacity-50"
              >
                {personaSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEdit && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4">Edit Project</h2>
            <form onSubmit={handleSave}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Project Name
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
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
                  placeholder="e.g., acme.com"
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Core Topics
                </label>
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
                      placeholder="Keywords (comma-separated)"
                    />
                    {editTopics.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setEditTopics(editTopics.filter((_, j) => j !== i))}
                        className="text-red-500 px-2"
                      >
                        x
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
                  onClick={() => setShowEdit(false)}
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
    </div>
  );
}
