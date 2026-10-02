import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import type { Data, Layout, PlotMouseEvent, PlotlyHTMLElement } from 'plotly.js';

export default function Chart({data, layout = {}, height = 300, onClick}: {data: Data[]; layout?: Partial<Layout>; height?: number; onClick?: (event: PlotMouseEvent) => void}) {
  const el = useRef<HTMLDivElement>(null);
  const click = useRef(onClick); click.current = onClick;
  useEffect(() => {
    const node = el.current!;
    const observer = new ResizeObserver(() => { if ((node as unknown as PlotlyHTMLElement).data) Plotly.Plots.resize(node); });
    observer.observe(node);
    return () => { observer.disconnect(); Plotly.purge(node); };
  }, []);
  useEffect(() => {
    const node = el.current!;
    let disposed = false;
    Plotly.react(node, data, { autosize: true, height, margin: { l: 48, r: 16, t: 12, b: 35 }, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { family: 'Segoe UI, sans-serif', color: '#748096', size: 11 }, hovermode: 'x unified', xaxis: { showgrid: false, zeroline: false }, yaxis: { gridcolor: '#edf0f5', zeroline: false }, showlegend: false, ...layout }, { responsive: true, displayModeBar: 'hover', displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'], toImageButtonOptions: {format: 'png', filename: 'shanghai-strategy-lab', scale: 2}, scrollZoom: false }).then(() => {
      if (disposed) return;
      const graph = node as unknown as PlotlyHTMLElement;
      graph.removeAllListeners('plotly_click');
      graph.on('plotly_click', event => click.current?.(event));
    });
    return () => { disposed = true; };
  }, [data, layout, height]);
  return <div className="chart" ref={el} style={{height}} aria-label="Interactive research chart" />;
}
