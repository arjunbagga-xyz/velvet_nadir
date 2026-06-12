// ── Memory Graph — D3 Force-Directed Graph ─────────────────
// Renders the MemPalace Knowledge Graph (live from bridge) or
// falls back to mock MEMORY_NODES/MEMORY_LINKS from data.js.

import { subscribe, state } from './ws-bridge.js';
import { MEMORY_NODES, MEMORY_LINKS } from './data.js'; // Fallback only

let graphInitialized = false;
let currentSimulation = null;

// Subscribe to live memory graph updates from the bridge
subscribe('memory', (graphData) => {
    if (graphData && graphData.nodes && graphData.nodes.length > 0) {
        rebuildGraph(graphData.nodes, graphData.links || []);
    }
});

export function initMemoryGraph() {
    const graph = state.memoryGraph;
    const nodes = graph?.nodes?.length ? graph.nodes : MEMORY_NODES;
    const links = graph?.links?.length ? graph.links : MEMORY_LINKS;
    rebuildGraph(nodes, links);
}

function rebuildGraph(sourceNodes, sourceLinks) {
    const container = document.getElementById('memory-graph');
    if (!container) return;

    // Wait for container to be visible and have dimensions
    requestAnimationFrame(() => {
        const width = container.clientWidth;
        const height = container.clientHeight;
        if (width === 0 || height === 0) {
            setTimeout(() => rebuildGraph(sourceNodes, sourceLinks), 100);
            return;
        }

        // Kill previous simulation if running
        if (currentSimulation) {
            currentSimulation.stop();
            currentSimulation = null;
        }

        graphInitialized = true;

        // Clear
        container.innerHTML = '';

        const svg = d3.select(container)
            .append('svg')
            .attr('width', width)
            .attr('height', height)
            .attr('viewBox', [0, 0, width, height])
            .style('max-width', '100%')
            .style('height', 'auto');

        // Zoom
        const g = svg.append('g');
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });
        svg.call(zoom);

        // Copy data
        const nodes = sourceNodes.map(d => ({ ...d }));
        const links = sourceLinks.map(d => ({ ...d }));

        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('x', d3.forceX(width / 2).strength(0.1))
            .force('y', d3.forceY(d => {
                if (d.tier === 1) return height * 0.2;
                if (d.tier === 2) return height * 0.5;
                if (d.tier === 3) return height * 0.8;
                return height / 2;
            }).strength(0.5))
            .force('collide', d3.forceCollide().radius(40));

        currentSimulation = simulation;

        // Links
        const link = g.append('g')
            .attr('stroke', '#333')
            .attr('stroke-opacity', 0.6)
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('stroke-width', d => Math.sqrt(d.value));

        // Link labels
        const linkLabel = g.append('g')
            .selectAll('text')
            .data(links)
            .join('text')
            .attr('font-size', '10px')
            .attr('fill', '#888')
            .attr('text-anchor', 'middle')
            .attr('font-family', "'Inter', sans-serif")
            .text(d => d.label);

        // Nodes
        function nodeColor(type) {
            switch (type) {
                case 'context': return '#8b5cf6';
                case 'agent': return '#3b82f6';
                case 'system': return '#10b981';
                case 'person': return '#f59e0b';
                case 'project': return '#ef4444';
                case 'material': return '#6366f1';
                case 'location': return '#14b8a6';
                case 'asset': return '#f43f5e';
                case 'event': return '#eab308';
                case 'tool': return '#06b6d4';
                case 'concept': return '#a855f7';
                default: return '#999';
            }
        }

        const node = g.append('g')
            .attr('stroke', '#fff')
            .attr('stroke-width', 1.5)
            .selectAll('circle')
            .data(nodes)
            .join('circle')
            .attr('r', 8)
            .attr('fill', d => nodeColor(d.type))
            .call(drag(simulation));

        // Node labels
        const nodeLabel = g.append('g')
            .selectAll('text')
            .data(nodes)
            .join('text')
            .attr('font-size', '12px')
            .attr('fill', '#f5f5f5')
            .attr('dx', 12)
            .attr('dy', 4)
            .attr('font-family', "'Inter', sans-serif")
            .text(d => d.id);

        node.append('title')
            .text(d => `${d.id} (${d.type})`);

        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            linkLabel
                .attr('x', d => (d.source.x + d.target.x) / 2)
                .attr('y', d => (d.source.y + d.target.y) / 2);

            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);

            nodeLabel
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        });

        // Drag
        function drag(simulation) {
            function dragstarted(event) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }
            function dragged(event) {
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }
            function dragended(event) {
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }
            return d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended);
        }
    });
}
