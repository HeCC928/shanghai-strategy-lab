import {useState} from 'react';
import Chart from './Chart';
type Row=Record<string,any>;
const pct=(v:unknown)=>typeof v==='number'?`${(v*100).toFixed(1)}%`:'—';
export default function RiskExposure({run}:{run:{config:Row;equity?:Row[];risk_states?:Row[]}}) {
  const [day,setDay]=useState('');
  const risk=(run.risk_states||[]).filter(x=>x.date>=run.config.start&&x.date<=run.config.end);
  const selected=risk.find(x=>x.date===day);
  return <section className="panel risk-panel"><div className="section-heading"><div><h2>Exposure, with context</h2><p>Closing target and actual invested weight. Orders act on a later session.</p></div><span className="tag">{run.config.market_filter?'TREND FILTER':run.config.volatility_control?'VOLATILITY ALLOCATION':'FIXED ALLOCATION'}</span></div><Chart height={170} data={[{type:'scatter',mode:'lines',x:run.equity?.map(e=>e.date),y:run.equity?.map(e=>e.exposure),line:{color:'#29a69b',width:2},fill:'tozeroy',fillcolor:'rgba(41,166,155,.07)',name:'Actual invested weight'},{type:'scatter',mode:'lines',x:risk.map(e=>e.date),y:risk.map(e=>e.target_exposure),line:{color:'#9272bf',dash:'dot',shape:'hv'},name:'Closing target exposure'}]} layout={{yaxis:{tickformat:'.0%',range:[0,1.08]},showlegend:true,legend:{orientation:'h',y:1.3}}} onClick={e=>setDay(String(e.points[0]?.x||''))}/><p className="chart-footnote">{selected?`${day} · Target ${pct(selected.target_exposure)} · ${selected.trend_allowed?'Trend permitted':'Defensive trend state'} · Market volatility ${pct(selected.market_volatility)}. Actual exposure also reflects cash, staged fills and market movement.`:'Click a date to inspect the recorded risk state. Volatility allocation uses trailing market-index volatility, not forecast portfolio volatility.'}</p></section>;
}
