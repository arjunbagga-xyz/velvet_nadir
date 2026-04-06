import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { MEMORY_NODES, MEMORY_LINKS } from '../data';

export default function MemoryGraph() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // Clear previous graph
    d3.select(containerRef.current).selectAll('*').remove();

    const svg = d3.select(containerRef.current)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .attr('style', 'max-width: 100%; height: auto;');

    // Add zoom capabilities
    const g = svg.append('g');
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    svg.call(zoom);

    // Copy data to avoid mutating original
    const nodes = MEMORY_NODES.map(d => ({ ...d }));
    const links = MEMORY_LINKS.map(d => ({ ...d }));

    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('x', d3.forceX(width / 2).strength(0.1))
      .force('y', d3.forceY((d: any) => {
        if (d.tier === 1) return height * 0.2;
        if (d.tier === 2) return height * 0.5;
        if (d.tier === 3) return height * 0.8;
        return height / 2;
      }).strength(0.5))
      .force('collide', d3.forceCollide().radius(40));

    // Draw links
    const link = g.append('g')
      .attr('stroke', '#333')
      .attr('stroke-opacity', 0.6)
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke-width', d => Math.sqrt(d.value));

    // Draw link labels
    const linkLabel = g.append('g')
      .selectAll('text')
      .data(links)
      .join('text')
      .attr('font-size', '10px')
      .attr('fill', '#888')
      .attr('text-anchor', 'middle')
      .text(d => d.label);

    // Draw nodes
    const node = g.append('g')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', 8)
      .attr('fill', (d: any) => {
        switch (d.type) {
          case 'context': return '#8b5cf6'; // purple
          case 'agent': return '#3b82f6'; // blue
          case 'system': return '#10b981'; // green
          case 'person': return '#f59e0b'; // amber
          case 'project': return '#ef4444'; // red
          case 'material': return '#6366f1'; // indigo
          case 'location': return '#14b8a6'; // teal
          case 'asset': return '#f43f5e'; // rose
          case 'event': return '#eab308'; // yellow
          default: return '#999';
        }
      })
      .call(drag(simulation) as any);

    // Draw node labels
    const nodeLabel = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .attr('font-size', '12px')
      .attr('fill', '#f5f5f5')
      .attr('dx', 12)
      .attr('dy', 4)
      .text(d => d.id);

    node.append('title')
      .text(d => `${d.id} (${d.type})`);

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      linkLabel
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2);

      node
        .attr('cx', (d: any) => d.x)
        .attr('cy', (d: any) => d.y);

      nodeLabel
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y);
    });

    // Drag function
    function drag(simulation: d3.Simulation<any, any>) {
      function dragstarted(event: any) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }
      
      function dragged(event: any) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }
      
      function dragended(event: any) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }
      
      return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended);
    }

    return () => {
      simulation.stop();
    };
  }, []);

  return <div ref={containerRef} className="w-full h-full min-h-[500px] bg-bg rounded-xl border border-border overflow-hidden" />;
}
