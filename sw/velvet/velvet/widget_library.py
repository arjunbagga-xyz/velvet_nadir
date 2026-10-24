"""
Generative UI Widget Library for Velvet Nadir

Handles state tracking and rendering directives for dynamically generated UI widgets.
Interfaces with Gateway to spawn interactive UI elements via the ws-bridge.
"""

from typing import Dict, Any, Callable
from loguru import logger
import uuid

class WidgetLibrary:
    def __init__(self, fabric=None):
        self.fabric = fabric
        self.active_widgets: Dict[str, Dict[str, Any]] = {}
        self.action_handlers: Dict[str, Callable] = {}
        
    async def spawn_widget(self, widget_type: str, title: str, description: str = "", custom_html: str = "", **kwargs) -> str:
        """
        Spawn a dynamic widget on the frontend.
        Types: 'media', 'model3d', 'generic'
        """
        widget_id = f"widget-{uuid.uuid4().hex[:8]}"
        widget_data = {
            "id": widget_id,
            "widget_type": widget_type,
            "title": title,
            "description": description,
            "custom_html": custom_html,
            **kwargs
        }
        
        self.active_widgets[widget_id] = widget_data
        
        if self.fabric:
            logger.info(f"[WidgetLibrary] Spawning widget {widget_id} of type {widget_type}")
            await self.fabric.publish("display/ui.widget.render", {"data": widget_data})
        else:
            logger.warning("[WidgetLibrary] Cannot spawn widget - Fabric not connected.")
            
        return widget_id
        
    def register_action_handler(self, widget_id: str, action_name: str, handler: Callable):
        """Register a callback for when a widget fires an action."""
        key = f"{widget_id}:{action_name}"
        self.action_handlers[key] = handler
        
    async def handle_action(self, widget_id: str, action: str, payload: dict):
        """Invoke the registered action handler."""
        key = f"{widget_id}:{action}"
        handler = self.action_handlers.get(key)
        if handler:
            try:
                await handler(payload)
            except Exception as e:
                logger.error(f"[WidgetLibrary] Error in action handler for {key}: {e}")
        else:
            logger.warning(f"[WidgetLibrary] No handler found for {key}")

    async def update_widget(self, widget_id: str, **kwargs):
        """Update a running widget's state."""
        if widget_id in self.active_widgets:
            self.active_widgets[widget_id].update(kwargs)
            if self.fabric:
                await self.fabric.publish("display/ui.widget.render", {"data": self.active_widgets[widget_id]})

    async def spawn_narrative_radar_brief(self, brief_data: Dict[str, Any]) -> str:
        """
        Spawn Daily Intelligence Brief widget with volume bars, virality indicators,
        security alerts, and physical event correlations.
        """
        html = (
            "<div class='narrative-brief-widget' style='padding: 1rem; color: #fff; background: #0f172a; border-radius: 8px; font-family: monospace;'>"
            "<h3 style='margin-top: 0; color: #38bdf8;'>🛰️ Daily Intelligence Brief</h3>"
            f"<div style='margin-bottom: 0.5rem; font-size: 0.85rem; color: #94a3b8;'>Active Branches: {', '.join(brief_data.get('active_branches', []))}</div>"
        )
        if brief_data.get("security_alerts"):
            html += "<div style='background: #7f1d1d; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.5rem; font-weight: bold;'>⚠️ SECURITY ALERTS:<br>"
            for alert in brief_data["security_alerts"]:
                html += f"• {alert}<br>"
            html += "</div>"

        html += "<div style='margin-top: 0.5rem;'><strong>Top Narratives & Virality:</strong><ul style='padding-left: 1.2rem;'>"
        for n in brief_data.get("top_narratives", []):
            score = n.get("virality", 0)
            color = "#ef4444" if score >= 70 else ("#f59e0b" if score >= 40 else "#10b981")
            html += (
                f"<li style='margin-bottom: 0.4rem;'><strong>{n.get('title')}</strong> "
                f"<span style='color: {color}; font-weight: bold;'>[{n.get('virality_classification')}: {score:.1f}% in {n.get('demographic')}]</span><br>"
                f"<span style='font-size: 0.8rem; color: #64748b;'>{n.get('alert', '')}</span></li>"
            )
        html += "</ul></div></div>"

        return await self.spawn_widget(
            widget_type="narrative_radar_brief",
            title="Daily Intelligence Brief",
            description="Intelligence narrative velocity and demographic virality",
            custom_html=html,
            brief_data=brief_data,
        )

    async def spawn_graph_explorer(self, graph_data: Dict[str, Any]) -> str:
        """
        Spawn interactive D3 force-directed intelligence graph explorer.
        Visualizes Power -> Amplifiers -> Demographics hierarchy.
        """
        nodes_count = len(graph_data.get("nodes", []))
        links_count = len(graph_data.get("links", []))
        html = (
            f"<div class='graph-explorer-widget' style='padding: 1rem; background: #090d16; border-radius: 8px; color: #fff;'>"
            f"<h3 style='color: #818cf8; margin-top: 0;'>🕸️ Intelligence Graph Explorer</h3>"
            f"<p style='font-size: 0.85rem; color: #94a3b8;'>Nodes: {nodes_count} | Triples: {links_count}</p>"
            f"<div id='d3-graph-container' style='width: 100%; height: 350px; background: #020617; border: 1px solid #1e293b; border-radius: 4px;'></div>"
            f"</div>"
        )
        return await self.spawn_widget(
            widget_type="graph_explorer",
            title="Intelligence Graph Explorer",
            description="3-Tier hierarchy: Power -> Amplifiers -> Demographics",
            custom_html=html,
            graph_data=graph_data,
        )

    async def spawn_honeypot_visualizer(self, port_map: Dict[str, int], grace_ports: Dict[str, int]) -> str:
        """
        Spawn Honeypot & Port Rotation visualizer.
        Displays randomized live mesh ports vs trapped standard ports.
        """
        html = (
            "<div class='honeypot-visualizer' style='padding: 1rem; background: #050811; border-radius: 8px; color: #fff;'>"
            "<h3 style='color: #22c55e; margin-top: 0;'>🛡️ Stealth Port Map & Honeypot Inversion</h3>"
            "<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;'>"
            "<div><strong style='color: #38bdf8;'>Active Randomized Ports:</strong><ul style='font-family: monospace;'>"
        )
        for svc, port in port_map.items():
            html += f"<li>{svc}: <span style='color: #4ade80;'>:{port}</span></li>"
        html += "</ul></div><div><strong style='color: #f43f5e;'>Honeypot Traps (0.0.0.0/0):</strong><ul style='font-family: monospace;'>"
        for p in [22, 80, 443, 2375, 3306, 5432, 5900, 6379, 8080, 8443, 9000, 27017]:
            html += f"<li>Port {p} <span style='color: #fb7185;'>[TRAP]</span></li>"
        html += "</ul></div></div></div>"

        return await self.spawn_widget(
            widget_type="honeypot_visualizer",
            title="Honeypot & Port Inversion",
            description="Real service ports vs open standard traps",
            custom_html=html,
            port_map=port_map,
            grace_ports=grace_ports,
        )
