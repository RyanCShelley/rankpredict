import { useState } from 'react';

const STAGES = [
  { id: 'Trigger / Awareness', color: '#6b7280', bgColor: 'bg-gray-100', textColor: 'text-gray-800' },
  { id: 'Exploration / Consideration', color: '#f97316', bgColor: 'bg-orange-100', textColor: 'text-orange-800' },
  { id: 'Narrowing / Evaluation', color: '#a855f7', bgColor: 'bg-purple-100', textColor: 'text-purple-800' },
  { id: 'Validation / Trust', color: '#3b82f6', bgColor: 'bg-blue-100', textColor: 'text-blue-800' },
  { id: 'Decision / Action', color: '#22c55e', bgColor: 'bg-green-100', textColor: 'text-green-800' },
];

export default function TopicFunnel({
  funnelData,
  onMoveKeyword,
  onDeleteKeyword,
  onGenerateQueries,
  onFetchVolumes,
  generatingStage,
  fetchingVolumes,
  loading
}) {
  const [expandedStages, setExpandedStages] = useState(new Set(STAGES.map(s => s.id)));
  const [selectedKeyword, setSelectedKeyword] = useState(null);
  const [showMoveModal, setShowMoveModal] = useState(false);

  const toggleStage = (stageId) => {
    const newExpanded = new Set(expandedStages);
    if (newExpanded.has(stageId)) {
      newExpanded.delete(stageId);
    } else {
      newExpanded.add(stageId);
    }
    setExpandedStages(newExpanded);
  };

  const handleMoveClick = (keyword) => {
    setSelectedKeyword(keyword);
    setShowMoveModal(true);
  };

  const handleMoveConfirm = (newStage) => {
    if (selectedKeyword && onMoveKeyword) {
      onMoveKeyword(selectedKeyword.id, newStage);
    }
    setShowMoveModal(false);
    setSelectedKeyword(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Loading funnel data...
      </div>
    );
  }

  if (!funnelData?.stages) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        No funnel data available
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50 p-4 overflow-hidden">
      {/* Funnel Visualization */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {STAGES.map((stage, index) => {
          const stageData = funnelData.stages[stage.id] || { keywords: [], total_volume: 0, avg_position: null, keyword_count: 0 };
          const isExpanded = expandedStages.has(stage.id);

          // Calculate funnel width (wider at top, narrower at bottom)
          const widthPercent = 100 - (index * 8);

          return (
            <div key={stage.id} className="relative">
              {/* Stage Header - Funnel Shape */}
              <div
                className="mx-auto transition-all duration-200"
                style={{ width: `${widthPercent}%` }}
              >
                <div
                  className="rounded-lg shadow cursor-pointer hover:shadow-md transition-shadow"
                  style={{ backgroundColor: stage.color }}
                  onClick={() => toggleStage(stage.id)}
                >
                  <div className="px-4 py-3 text-white">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-lg">{isExpanded ? '▼' : '▶'}</span>
                        <div>
                          <h3 className="font-semibold text-base">{stage.id}</h3>
                          <div className="text-sm opacity-90">
                            {stageData.keyword_count} keywords
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-6 text-sm">
                        <div className="text-center">
                          <div className="opacity-75">Volume</div>
                          <div className="font-semibold">{(stageData.total_volume || 0).toLocaleString()}</div>
                        </div>
                        <div className="text-center">
                          <div className="opacity-75">Clicks</div>
                          <div className="font-semibold">{(stageData.total_clicks || 0).toLocaleString()}</div>
                        </div>
                        <div className="text-center">
                          <div className="opacity-75">Avg Pos</div>
                          <div className="font-semibold">{stageData.avg_position || '-'}</div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onFetchVolumes?.(stage.id);
                          }}
                          disabled={fetchingVolumes === stage.id}
                          className="bg-white/20 hover:bg-white/30 px-3 py-1 rounded text-xs font-medium disabled:opacity-50"
                        >
                          {fetchingVolumes === stage.id ? 'Fetching...' : 'Get Volumes'}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onGenerateQueries?.(stage.id);
                          }}
                          disabled={generatingStage === stage.id}
                          className="bg-white/20 hover:bg-white/30 px-3 py-1 rounded text-xs font-medium disabled:opacity-50"
                        >
                          {generatingStage === stage.id ? 'Generating...' : '+ Find Queries'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Keywords List */}
                {isExpanded && stageData.keywords.length > 0 && (
                  <div className="mt-2 bg-white rounded-lg shadow overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">Query</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">Page URL</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">Clicks</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">Vol</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">Pos</th>
                          <th className="text-center px-3 py-2 font-medium text-gray-600">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stageData.keywords.map((kw) => (
                          <tr key={kw.id} className={`border-b hover:bg-gray-50 ${kw.is_ai_generated ? 'bg-yellow-50' : ''}`}>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                {kw.is_ai_generated && (
                                  <span className="text-xs bg-yellow-200 text-yellow-800 px-1.5 py-0.5 rounded" title="AI Generated">
                                    AI
                                  </span>
                                )}
                                <span className="font-medium truncate max-w-xs" title={kw.query}>
                                  {kw.query}
                                </span>
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              {kw.page_url ? (
                                <a
                                  href={kw.page_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:underline truncate block max-w-xs"
                                  title={kw.page_url}
                                >
                                  {kw.page_url.replace(/^https?:\/\//, '').slice(0, 40)}...
                                </a>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-right">{kw.clicks?.toLocaleString() || 0}</td>
                            <td className="px-3 py-2 text-right">{kw.volume?.toLocaleString() || '-'}</td>
                            <td className="px-3 py-2 text-right">
                              {kw.avg_position ? kw.avg_position.toFixed(1) : '-'}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <div className="flex items-center justify-center gap-1">
                                <button
                                  onClick={() => handleMoveClick(kw)}
                                  className="text-gray-500 hover:text-blue-600 p-1"
                                  title="Move to different stage"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                                  </svg>
                                </button>
                                <button
                                  onClick={() => onDeleteKeyword?.(kw.id)}
                                  className="text-gray-500 hover:text-red-600 p-1"
                                  title="Delete keyword"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {isExpanded && stageData.keywords.length === 0 && (
                  <div className="mt-2 bg-white rounded-lg shadow p-4 text-center text-gray-500 text-sm">
                    No keywords in this stage. Click "Find Queries" to generate some.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Move Keyword Modal */}
      {showMoveModal && selectedKeyword && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-md p-6">
            <h2 className="text-lg font-bold mb-4">Move Keyword to Stage</h2>
            <p className="text-sm text-gray-600 mb-4">
              Moving: <strong>{selectedKeyword.query}</strong>
            </p>
            <div className="space-y-2">
              {STAGES.map((stage) => (
                <button
                  key={stage.id}
                  onClick={() => handleMoveConfirm(stage.id)}
                  className={`w-full text-left px-4 py-3 rounded-lg border hover:border-gray-400 transition-colors ${stage.bgColor}`}
                >
                  <span className={`font-medium ${stage.textColor}`}>{stage.id}</span>
                </button>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => {
                  setShowMoveModal(false);
                  setSelectedKeyword(null);
                }}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
