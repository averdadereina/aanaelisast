import json
import re
import subprocess
from pathlib import Path

data_path = Path('posts-data.json')
posts = json.loads(data_path.read_text())
script = r'''async () => {
 const entries=__ENTRIES__;
 const results=[];
 for(let offset=0;offset<entries.length;offset+=8){
  const batch=entries.slice(offset,offset+8);
  const part=await Promise.all(batch.map(async entry=>{
   for(const url of entry.urls){
    try{
     const response=await fetch(url,{credentials:'include'});
     const source=await response.text();
     const doc=new DOMParser().parseFromString(source,'text/html');
     const article=doc.querySelector('article');
     if(!article) continue;
     const body=article.innerText||'';
     if(!doc.title.includes('Ana Elisa on X')&&!body.includes('@aanaelisast')) continue;
     const dateMatch=body.match(/\d{1,2}:\d{2}\s*(?:AM|PM)\s*·\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4}/);
     const markers=['Show translation','Translate post','Traduzir post'];
     let marker=-1,markerLength=0;
     for(const item of markers){const index=body.lastIndexOf(item);if(index>marker){marker=index;markerLength=item.length;}}
     const startAt=marker>=0?marker+markerLength:Math.max(body.indexOf('@aanaelisast')+13,0);
     const text=body.slice(startAt,dateMatch?dateMatch.index:body.length).replace(/\n+$/,'').trim();
     if(text)return{id:entry.id,url,text,published:dateMatch?dateMatch[0]:''};
    }catch(error){}
   }
   return{id:entry.id,missing:true};
  }));
  results.push(...part);
 }
 return results;
}'''

for offset in range(0, len(posts), 8):
    batch = posts[offset:offset + 8]
    entries = [{'id': post['id'], 'urls': post.get('archives', [])} for post in batch]
    expression = script.replace('__ENTRIES__', json.dumps(entries, ensure_ascii=False))
    result = subprocess.run(
        ['playwright-cli', '-s=local-archive', 'eval', expression],
        capture_output=True, text=True, timeout=180,
    )
    if result.returncode:
        print(f'lote {offset + 1}-{offset + len(batch)} falhou: {result.stderr[-300:]}', flush=True)
        continue
    try:
        payload = result.stdout.split('### Result\n', 1)[1].split('\n### Ran Playwright code', 1)[0]
        extracted = json.loads(payload)
    except (IndexError, json.JSONDecodeError) as error:
        print(f'lote {offset + 1}-{offset + len(batch)}: retorno inválido ({error})', flush=True)
        continue
    by_id = {item['id']: item for item in extracted if item and not item.get('missing')}
    for post in batch:
        item = by_id.get(post['id'])
        if item:
            post['text'] = item['text']
            post['published'] = item['published']
            post['source_archive'] = item['url']
    data_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2))
    complete = sum(bool(post.get('published')) for post in posts)
    print(f'{offset + len(batch)}/{len(posts)} verificados; {complete} com texto e horário', flush=True)
