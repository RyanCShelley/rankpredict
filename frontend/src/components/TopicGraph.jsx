import { useState, useEffect, useRef } from 'react';

const STAGE_COLORS = {
  'Decision / Action': '#22c55e',
  'Validation / Trust': '#3b82f6',
  'Narrowing / Evaluation': '#a855f7',
  'Exploration / Consideration': '#f97316',
  'Trigger / Awareness': '#6b7280'
};

export default function TopicGraph({ nodes, edges, onNodeClick }) {
  const svgRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState(null);

  useEffect(() => {
    const updateDimensions = () => {
      if (svgRef.current?.parentElement) {
        const rect = svgRef.current.parentElement.getBoundingClientRect();
        setDimensions({ width: rect.width, height: rect.height });
      }
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Pan handlers
  const handleMouseDown = (e) => {
    if (e.target === svgRef.current) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setTransform(prev => ({
        ...prev,
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      }));
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Zoom handler
  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform(prev => ({
      ...prev,
      scale: Math.max(0.3, Math.min(2, prev.scale * delta))
    }));
  };

  // Find topic node (center)
  const topicNode = nodes.find(n => n.type === 'topic');
  const keywordNodes = nodes.filter(n => n.type === 'keyword');

  if (!topicNode || keywordNodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        No data to visualize
      </div>
    );
  }

  // Center offset
  const centerX = dimensions.width / 2;
  const centerY = dimensions.height / 2;

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      {/* Legend */}
      <div className="absolute top-4 left-4 bg-white/90 rounded-lg p-3 text-xs z-10">
        <div className="font-medium mb-2">Journey Stages</div>
        {Object.entries(STAGE_COLORS).map(([stage, color]) => (
          <div key={stage} className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span>{stage}</span>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="absolute top-4 right-4 bg-white/90 rounded-lg p-2 z-10 flex gap-2">
        <button
          onClick={() => setTransform(prev => ({ ...prev, scale: Math.min(2, prev.scale * 1.2) }))}
          className="w-8 h-8 flex items-center justify-center hover:bg-gray-100 rounded"
        >
          +
        </button>
        <button
          onClick={() => setTransform(prev => ({ ...prev, scale: Math.max(0.3, prev.scale * 0.8) }))}
          className="w-8 h-8 flex items-center justify-center hover:bg-gray-100 rounded"
        >
          -
        </button>
        <button
          onClick={() => setTransform({ x: 0, y: 0, scale: 1 })}
          className="w-8 h-8 flex items-center justify-center hover:bg-gray-100 rounded text-xs"
        >
          Reset
        </button>
      </div>

      {/* Hovered Node Info */}
      {hoveredNode && (
        <div className="absolute bottom-4 left-4 bg-white rounded-lg p-3 shadow-lg z-10 max-w-xs">
          <div className="font-medium">{hoveredNode.label}</div>
          {hoveredNode.stage && (
            <div className="text-sm text-gray-600 mt-1">
              Stage: {hoveredNode.stage}
            </div>
          )}
          {hoveredNode.clicks !== undefined && (
            <div className="text-sm text-gray-600">
              Clicks: {hoveredNode.clicks?.toLocaleString()}
            </div>
          )}
        </div>
      )}

      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
          {/* Edges */}
          {edges.map(edge => {
            const source = nodes.find(n => n.id === edge.source);
            const target = nodes.find(n => n.id === edge.target);
            if (!source || !target) return null;

            const sourceX = source.x - 400 + centerX;
            const sourceY = source.y - 300 + centerY;
            const targetX = target.x - 400 + centerX;
            const targetY = target.y - 300 + centerY;

            return (
              <line
                key={edge.id}
                x1={sourceX}
                y1={sourceY}
                x2={targetX}
                y2={targetY}
                stroke="#4b5563"
                strokeWidth={Math.max(1, (edge.weight || 0.5) * 3)}
                strokeOpacity={0.4}
              />
            );
          })}

          {/* Keyword Nodes */}
          {keywordNodes.map(node => {
            const x = node.x - 400 + centerX;
            const y = node.y - 300 + centerY;
            const color = node.color || STAGE_COLORS[node.stage] || '#6b7280';
            const isHovered = hoveredNode?.id === node.id;

            return (
              <g
                key={node.id}
                transform={`translate(${x}, ${y})`}
                onMouseEnter={() => setHoveredNode(node)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => onNodeClick?.(node)}
                style={{ cursor: 'pointer' }}
              >
                <circle
                  r={isHovered ? 12 : 8}
                  fill={color}
                  stroke="#fff"
                  strokeWidth={2}
                  opacity={isHovered ? 1 : 0.8}
                />
                {isHovered && (
                  <text
                    y={-15}
                    textAnchor="middle"
                    fill="#fff"
                    fontSize={12}
                    fontWeight="bold"
                  >
                    {node.label.length > 30 ? node.label.slice(0, 30) + '...' : node.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Topic Node (Center) */}
          <g transform={`translate(${centerX}, ${centerY})`}>
            <circle
              r={40}
              fill="#223540"
              stroke="#fff"
              strokeWidth={3}
            />
            <text
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#fff"
              fontSize={12}
              fontWeight="bold"
            >
              {topicNode.label.length > 15 ? topicNode.label.slice(0, 15) + '...' : topicNode.label}
            </text>
          </g>
        </g>
      </svg>
    </div>
  );
}
