const API_BASE = "https://haven-ai-nanny-pro-starter.onrender.com";

let child = {name:"Ava", age_years:4.0, language:"en", temperament:"balanced"};

document.getElementById('saveChild').onclick = async () => {
  child = {
    name: document.getElementById('cname').value || "Your child",
    age_years: parseFloat(document.getElementById('cage').value || "4.0"),
    language: document.getElementById('clang').value,
    temperament: "balanced"
  };
  const res = await fetch(API_BASE + "/child", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(child)});
  const data = await res.json();
  document.getElementById('childStatus').textContent = data.ok ? "Saved!" : "Failed";
};

document.getElementById('suggestAct').onclick = async () => {
  const minutes = parseInt(document.getElementById('amin').value || "20");
  const mode = document.getElementById('amode').value;
  const res = await fetch(API_BASE + "/activities/suggest", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({child, minutes, mode})});
  const data = await res.json();
  document.getElementById('actOut').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('storyBtn').onclick = async () => {
  const res = await fetch(API_BASE + "/story/generate", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({child, theme: document.getElementById('theme').value, bilingual: document.getElementById('bilingual').checked})});
  const data = await res.json();
  document.getElementById('storyOut').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('sessionBtn').onclick = async () => {
  const res = await fetch(API_BASE + "/session/start", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({child, duration_min:30, goal:"engage"})});
  const data = await res.json();
  document.getElementById('sessionOut').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('metricsBtn').onclick = async () => {
  const res = await fetch(API_BASE + "/metrics/timesaved");
  const data = await res.json();
  document.getElementById('metricsOut').textContent = JSON.stringify(data, null, 2);
};
