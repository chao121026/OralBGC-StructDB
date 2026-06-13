window.renderHomeChart=function(charts){
  if(!window.Plotly || !charts) return;
  const palette=['#007c89','#09233d','#b56b1d','#5b6f82','#2b8a3e','#6b5fb5'];
  const renderBar=(id,data,xTitle='Records')=>{
    const el=document.getElementById(id);
    if(!el || !data) return;
    const labels=data.map(d=>d.label || 'Not available');
    const values=data.map(d=>d.value);
    Plotly.newPlot(el,[{type:'bar',x:values,y:labels,orientation:'h',marker:{color:palette[0]}}],
      {margin:{l:135,r:16,t:8,b:34},paper_bgcolor:'white',plot_bgcolor:'white',xaxis:{title:xTitle},yaxis:{automargin:true},font:{family:'Inter, Source Sans 3, system-ui, sans-serif',size:11}},
      {responsive:true,displaylogo:false});
  };
  const renderDonut=(id,data)=>{
    const el=document.getElementById(id);
    if(!el || !data) return;
    Plotly.newPlot(el,[{type:'pie',labels:data.map(d=>d.label || 'Not available'),values:data.map(d=>d.value),hole:.48,marker:{colors:palette},textinfo:'label+percent',textposition:'auto'}],
      {margin:{l:8,r:8,t:8,b:8},paper_bgcolor:'white',font:{family:'Inter, Source Sans 3, system-ui, sans-serif',size:11},showlegend:false},
      {responsive:true,displaylogo:false});
  };
  renderBar('chart-bgc-class',charts.bgc_class,'Proteins');
  renderDonut('chart-confidence',charts.confidence);
  renderDonut('chart-length',charts.length_bucket);
  renderBar('chart-pdb-category',charts.pdb_category,'Proteins');
}
