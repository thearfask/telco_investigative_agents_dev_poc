from __future__ import annotations
import plotly.graph_objects as go
from tools import data, build_graph

def topology_figure(failed_link=None, affected_nodes=None, restoration_links=None):
    affected_nodes = set(affected_nodes or [])
    restoration_links = set(restoration_links or [])
    g = build_graph()

    y_by_type = {"core_router":4.0,"pe_router":3.2,"aggregation_router":2.35,"access_router":1.25,"cell_site":0.15}
    x_by_domain = {"CORE":-3.3,"METRO-A":-1.45,"METRO-B":0.8,"METRO-C":3.0}
    buckets, pos = {}, {}
    for n,a in g.nodes(data=True):
        buckets.setdefault((a.get("domain"),a.get("node_type")),[]).append(n)
    for (domain,ntype), ns in buckets.items():
        ns=sorted(ns)
        for i,n in enumerate(ns):
            pos[n]=(x_by_domain.get(domain,0)+(i-(len(ns)-1)/2)*0.34,y_by_type.get(ntype,0))

    fig=go.Figure()
    for u,v,a in g.edges(data=True):
        lid=a.get("link_id"); x0,y0=pos[u]; x1,y1=pos[v]
        if lid==failed_link:
            color,width,dash="#ff4b4b",5,"dash"
        elif lid in restoration_links:
            color,width,dash="#4f8cff",4,"solid"
        else:
            color,width,dash="#3e9f62",1.5,"solid"
        fig.add_trace(go.Scatter(
            x=[x0,x1],y=[y0,y1],mode="lines",
            line=dict(color=color,width=width,dash=dash),
            text=[f"{lid}<br>{u} ↔ {v}"]*2,hoverinfo="text",showlegend=False
        ))

    xs=[];ys=[];texts=[];colors=[];sizes=[];symbols=[]
    for n,a in g.nodes(data=True):
        x,y=pos[n];xs.append(x);ys.append(y)
        texts.append(f"<b>{n}</b><br>{a.get('node_type')}<br>{a.get('domain')}")
        if n in affected_nodes: colors.append("#ef5350"); sizes.append(18)
        elif a.get("node_type") in {"core_router","pe_router","aggregation_router"}: colors.append("#63c174");sizes.append(18)
        else: colors.append("#72b983");sizes.append(13)
        symbols.append("circle")
    fig.add_trace(go.Scatter(
        x=xs,y=ys,mode="markers+text",
        marker=dict(size=sizes,color=colors,line=dict(width=1.2,color="#0b1118")),
        text=[t.split("<br>")[0].replace("<b>","").replace("</b>","") for t in texts],
        textposition="bottom center",textfont=dict(size=9,color="#d9e2ec"),
        customdata=texts,hovertemplate="%{customdata}<extra></extra>",showlegend=False
    ))
    fig.update_layout(
        height=500,margin=dict(l=5,r=5,t=10,b=5),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),yaxis=dict(visible=False),hovermode="closest",
    )
    return fig
