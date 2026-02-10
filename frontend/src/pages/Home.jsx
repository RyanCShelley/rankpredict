import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { strategyDevAPI } from '../services/api';

export default function Home() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  // New project modal
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [topics, setTopics] = useState([{ name: '', keywords: '' }]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const data = await strategyDevAPI.getProjects();
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    const coreTopics = topics
      .filter(t => t.name.trim())
      .map(t => ({
        name: t.name.trim(),
        keywords: t.keywords.split(',').map(k => k.trim()).filter(k => k)
      }));

    setCreating(true);
    try {
      const project = await strategyDevAPI.createProject(
        name,
        domain || null,
        coreTopics.length ? coreTopics : null
      );
      setProjects([project, ...projects]);
      setShowModal(false);
      setName('');
      setDomain('');
      setTopics([{ name: '', keywords: '' }]);
    } catch (err) {
      console.error('Failed to create project:', err);
      alert('Failed to create project');
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading projects...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-gray-500 mt-1">Manage your SEO strategy projects</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-[#223540] text-white px-5 py-2.5 rounded-lg hover:bg-[#2d4654] text-sm font-medium"
        >
          + New Project
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-lg shadow-sm">
          <div className="text-gray-400 text-5xl mb-4">+</div>
          <h3 className="text-lg font-medium text-gray-700 mb-2">No projects yet</h3>
          <p className="text-gray-500 mb-6">Create your first project to get started</p>
          <button
            onClick={() => setShowModal(true)}
            className="bg-[#223540] text-white px-5 py-2.5 rounded-lg hover:bg-[#2d4654] text-sm font-medium"
          >
            Create Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map(p => (
            <div
              key={p.id}
              onClick={() => navigate(`/project/${p.id}`)}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-[#223540]/30 transition-all cursor-pointer"
            >
              <div className="flex justify-between items-start mb-3">
                <h3 className="font-semibold text-gray-900 text-lg">{p.name}</h3>
                {p.gsc_connected ? (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">GSC</span>
                ) : (
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">No GSC</span>
                )}
              </div>
              {p.domain && (
                <p className="text-sm text-gray-500 mb-4 truncate">{p.domain}</p>
              )}
              {!p.domain && <div className="mb-4" />}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-[#223540]">{p.num_funnels || 0}</div>
                  <div className="text-xs text-gray-500">Funnels</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-[#223540]">{p.num_terms || 0}</div>
                  <div className="text-xs text-gray-500">Terms</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-lg font-bold text-[#223540]">{p.num_briefs || 0}</div>
                  <div className="text-xs text-gray-500">Briefs</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New Project Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-lg p-6">
            <h2 className="text-lg font-bold mb-4">Create New Project</h2>
            <form onSubmit={handleCreate}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  placeholder="e.g., Acme Corp"
                  required
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Domain
                </label>
                <input
                  type="text"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  placeholder="e.g., acme.com"
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Core Topics (Optional)
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Define topics to classify keywords. Add example keywords for each topic.
                </p>
                {topics.map((topic, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={topic.name}
                      onChange={(e) => {
                        const next = [...topics];
                        next[i].name = e.target.value;
                        setTopics(next);
                      }}
                      className="flex-1 border rounded px-3 py-2 text-sm"
                      placeholder="Topic name"
                    />
                    <input
                      type="text"
                      value={topic.keywords}
                      onChange={(e) => {
                        const next = [...topics];
                        next[i].keywords = e.target.value;
                        setTopics(next);
                      }}
                      className="flex-1 border rounded px-3 py-2 text-sm"
                      placeholder="Example keywords (comma-separated)"
                    />
                    {topics.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setTopics(topics.filter((_, j) => j !== i))}
                        className="text-red-500 px-2"
                      >
                        x
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setTopics([...topics, { name: '', keywords: '' }])}
                  className="text-sm text-blue-600 hover:underline"
                >
                  + Add Topic
                </button>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 bg-[#223540] text-white rounded hover:bg-[#2d4654] disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
