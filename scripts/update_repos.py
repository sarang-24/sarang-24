import os
import urllib.request
import json

# Configurations
USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "sarang-24")
EXCLUDED_REPOS = {USERNAME.lower(), "gitu", "sarang-24"}
PINNED_REPOS = {"awesome-agentic-ai"}
README_PATH = os.environ.get("README_PATH", "README.md")

# Language Badge Styling Config
LANGUAGE_THEMES = {
    'Python': {'color': '3776AB', 'logo': 'python'},
    'JavaScript': {'color': 'F7DF1E', 'logo': 'javascript'},
    'TypeScript': {'color': '007ACC', 'logo': 'typescript'},
    'HTML': {'color': 'E34F26', 'logo': 'html5'},
    'CSS': {'color': '1572B6', 'logo': 'css3'},
    'Shell': {'color': '89e051', 'logo': 'gnu-bash'},
    'C++': {'color': '00599C', 'logo': 'cplusplus'},
    'C': {'color': 'A8B9CC', 'logo': 'c'},
    'Java': {'color': '007396', 'logo': 'openjdk'},
    'Go': {'color': '00ADD8', 'logo': 'go'},
    'Rust': {'color': '000000', 'logo': 'rust'},
    'Jupyter Notebook': {'color': 'DA5B0B', 'logo': 'jupyter'},
}

def make_language_badge(lang):
    if not lang:
        return ""
    theme = LANGUAGE_THEMES.get(lang)
    lang_clean = lang.replace('-', '--').replace(' ', '_')
    if theme:
        return f'<img src="https://img.shields.io/badge/{lang_clean}-{theme["color"]}?style=flat-square&logo={theme["logo"]}&logoColor=white" alt="{lang}" />'
    else:
        return f'<img src="https://img.shields.io/badge/{lang_clean}-555555?style=flat-square" alt="{lang}" />'

def main():
    print(f"Fetching repositories for user: {USERNAME}")
    url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner"
    
    headers = {"User-Agent": "GitHub-Action-Update-Readme"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            repos = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching repositories: {e}")
        return

    # Filter out forks and excluded repos
    filtered_repos = []
    for r in repos:
        name = r.get('name', '')
        if r.get('fork') or name.lower() in EXCLUDED_REPOS or r.get('private'):
            continue
        filtered_repos.append(r)
        
    # Sort repos: stars (desc), pushed_at (desc)
    filtered_repos.sort(key=lambda r: (r.get('stargazers_count', 0), r.get('pushed_at', '') or r.get('updated_at', '')), reverse=True)
    
    # Prioritize pinned repos to the front
    pinned = [r for r in filtered_repos if r.get('name', '').lower() in PINNED_REPOS]
    unpinned = [r for r in filtered_repos if r.get('name', '').lower() not in PINNED_REPOS]
    final_repos = pinned + unpinned
    
    print(f"Found {len(final_repos)} public non-fork repositories.")
    
    # We will showcase top 6 in a grid
    featured = final_repos[:6]
    remaining = final_repos[6:]
    
    # Build featured repos HTML grid
    grid_html = '<table width="100%" border="0">\n'
    for i in range(0, len(featured), 2):
        grid_html += '  <tr>\n'
        for j in range(2):
            if i + j < len(featured):
                repo = featured[i + j]
                name = repo.get('name', '')
                desc = repo.get('description', '') or 'No description provided.'
                # Truncate description if too long to maintain neat visual alignment
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                html_url = repo.get('html_url', '')
                lang = repo.get('language', '')
                lang_badge = make_language_badge(lang)
                owner = repo.get('owner', {}).get('login', USERNAME)
                
                grid_html += f'''    <td width="50%" valign="top">
      <h4><a href="{html_url}">📁 {name}</a></h4>
      <p style="font-size: 14px;">{desc}</p>
      <p>{lang_badge} <img src="https://img.shields.io/github/stars/{owner}/{name}?style=flat-square&logo=github&color=F5C211" alt="stars" /> <img src="https://img.shields.io/github/forks/{owner}/{name}?style=flat-square&logo=github&color=58A6FF" alt="forks" /></p>
    </td>\n'''
            else:
                grid_html += '    <td width="50%" valign="top"></td>\n'
        grid_html += '  </tr>\n'
    grid_html += '</table>\n'
    
    # Build remaining repos table list
    remaining_html = ""
    if remaining:
        remaining_html += f'<br/>\n<details>\n  <summary><b>🔍 View All Repositories ({len(filtered_repos)})</b></summary>\n  <br/>\n'
        remaining_html += '  <table width="100%">\n    <thead>\n      <tr>\n        <th align="left">Repository</th>\n        <th align="left">Description</th>\n        <th align="center">Language</th>\n        <th align="center">Stars</th>\n      </tr>\n    </thead>\n    <tbody>\n'
        for repo in remaining:
            name = repo.get('name', '')
            desc = repo.get('description', '') or '-'
            html_url = repo.get('html_url', '')
            lang = repo.get('language', '') or '-'
            stars = repo.get('stargazers_count', 0)
            
            remaining_html += f'      <tr>\n        <td><b><a href="{html_url}">{name}</a></b></td>\n        <td>{desc}</td>\n        <td align="center">`{lang}`</td>\n        <td align="center">⭐ {stars}</td>\n      </tr>\n'
        remaining_html += '    </tbody>\n  </table>\n</details>\n'
        
    dynamic_content = f"{grid_html}{remaining_html}"
    
    # Read README.md
    if not os.path.exists(README_PATH):
        print(f"Error: README file not found at {README_PATH}")
        return
        
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_content = f.read()
        
    # Replace content between tags safely
    start_tag = "<!-- REPOSITORIES-LIST:START -->"
    end_tag = "<!-- REPOSITORIES-LIST:END -->"
    
    if start_tag not in readme_content or end_tag not in readme_content:
        print("Warning: Could not find repository comment tags in README.md")
        return
        
    start_idx = readme_content.find(start_tag) + len(start_tag)
    end_idx = readme_content.find(end_tag)
    
    new_readme_content = (
        readme_content[:start_idx]
        + "\n"
        + dynamic_content
        + "\n"
        + readme_content[end_idx:]
    )
        
    # Write back to README.md
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_readme_content)
        
    print("Successfully updated README.md with latest repository stats!")

if __name__ == "__main__":
    main()
