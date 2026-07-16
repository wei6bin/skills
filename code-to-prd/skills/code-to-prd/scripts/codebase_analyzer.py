#!/usr/bin/env python3
"""Analyze any codebase (frontend, backend, mobile, or fullstack) and extract routes, APIs, models, and structure.

Supports: React, Vue, Angular, Svelte, Next.js, Nuxt, NestJS, Express, Django, FastAPI, Flask,
.NET / ASP.NET (Web API, WCF, Web Forms), native Android (Java/Kotlin), native iOS (Swift/Objective-C).
Stdlib only — no third-party dependencies. Outputs JSON for downstream PRD generation.

Usage:
    python3 codebase_analyzer.py /path/to/project
    python3 codebase_analyzer.py /path/to/project --output prd-analysis.json
    python3 codebase_analyzer.py /path/to/project --format markdown
"""

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

IGNORED_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "coverage",
    "venv", ".venv", "__pycache__", ".nuxt", ".output", ".cache",
    ".turbo", ".vercel", "out", "storybook-static",
    ".tox", ".mypy_cache", ".pytest_cache", "htmlcov", "staticfiles",
    "media", "migrations", "egg-info",
    # .NET build output
    "bin", "obj", "packages",
    # Android build output
    ".gradle", ".idea",
    # iOS build output / vendored deps
    "Pods", "DerivedData", "xcuserdata", "Carthage",
}

FRAMEWORK_SIGNALS = {
    "react": ["react", "react-dom"],
    "next": ["next"],
    "vue": ["vue"],
    "nuxt": ["nuxt"],
    "angular": ["@angular/core"],
    "svelte": ["svelte"],
    "sveltekit": ["@sveltejs/kit"],
    "solid": ["solid-js"],
    "astro": ["astro"],
    "remix": ["@remix-run/react"],
    "nestjs": ["@nestjs/core"],
    "express": ["express"],
    "fastify": ["fastify"],
}

# Python backend frameworks detected via project files (no package.json)
PYTHON_FRAMEWORK_FILES = {
    "django": ["manage.py", "settings.py"],
    "fastapi": ["main.py"],  # confirmed via imports
    "flask": ["app.py"],      # confirmed via imports
}

ROUTE_FILE_PATTERNS = [
    "**/router.{ts,tsx,js,jsx}",
    "**/routes.{ts,tsx,js,jsx}",
    "**/routing.{ts,tsx,js,jsx}",
    "**/app-routing*.{ts,tsx,js,jsx}",
]

ROUTE_DIR_PATTERNS = [
    "pages", "views", "routes", "app",
    "src/pages", "src/views", "src/routes", "src/app",
]

API_DIR_PATTERNS = [
    "api", "services", "requests", "endpoints", "client",
    "src/api", "src/services", "src/requests",
]

STATE_DIR_PATTERNS = [
    "store", "stores", "models", "context", "state",
    "src/store", "src/stores", "src/models", "src/context",
]

I18N_DIR_PATTERNS = [
    "locales", "i18n", "lang", "translations", "messages",
    "src/locales", "src/i18n", "src/lang",
]

# Backend-specific directory patterns
CONTROLLER_DIR_PATTERNS = [
    "controllers", "src/controllers", "src/modules",
]

MODEL_DIR_PATTERNS = [
    "models", "entities", "src/entities", "src/models",
]

DTO_DIR_PATTERNS = [
    "dto", "dtos", "src/dto", "serializers",
]

MOCK_SIGNALS = [
    r"setTimeout\s*\(.*\breturn\b",
    r"Promise\.resolve\s*\(",
    r"\.mock\.",
    r"__mocks__",
    r"mockData",
    r"mock[A-Z]",
    r"faker\.",
    r"fixtures?/",
]

REAL_API_SIGNALS = [
    r"\baxios\b",
    r"\bfetch\s*\(",
    r"httpGet|httpPost|httpPut|httpDelete|httpPatch",
    r"\.get\s*\(\s*['\"`/]",
    r"\.post\s*\(\s*['\"`/]",
    r"\.put\s*\(\s*['\"`/]",
    r"\.delete\s*\(\s*['\"`/]",
    r"\.patch\s*\(\s*['\"`/]",
    r"useSWR|useQuery|useMutation",
    r"\$http\.",
    r"this\.http\.",
]

ROUTE_PATTERNS = [
    # React Router
    r'<Route\s+[^>]*path\s*=\s*["\']([^"\']+)["\']',
    r'path\s*:\s*["\']([^"\']+)["\']',
    # Vue Router
    r'path\s*:\s*["\']([^"\']+)["\']',
    # Angular
    r'path\s*:\s*["\']([^"\']+)["\']',
]

API_PATH_PATTERNS = [
    r'["\'](?:GET|POST|PUT|DELETE|PATCH)["\'].*?["\'](/[a-zA-Z0-9/_\-:{}]+)["\']',
    r'(?:get|post|put|delete|patch)\s*\(\s*["\'](/[a-zA-Z0-9/_\-:{}]+)["\']',
    r'(?:url|path|endpoint|baseURL)\s*[:=]\s*["\'](/[a-zA-Z0-9/_\-:{}]+)["\']',
    r'fetch\s*\(\s*[`"\'](?:https?://[^/]+)?(/[a-zA-Z0-9/_\-:{}]+)',
]

COMPONENT_EXTENSIONS = {
    ".tsx", ".jsx", ".vue", ".svelte", ".astro",
    ".cs", ".java", ".kt", ".swift",
}
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte", ".astro", ".py",
    # .NET / ASP.NET
    ".cs", ".aspx", ".ascx", ".cshtml",
    # Native Android
    ".java", ".kt", ".xml",
    # Native iOS
    ".swift", ".m", ".h", ".storyboard", ".xib",
}

# NestJS decorator patterns
NEST_ROUTE_PATTERNS = [
    r"@(?:Get|Post|Put|Delete|Patch|Head|Options|All)\s*\(\s*['\"]([^'\"]*)['\"]",
    r"@Controller\s*\(\s*['\"]([^'\"]*)['\"]",
]

# Django URL patterns
DJANGO_ROUTE_PATTERNS = [
    r"path\s*\(\s*['\"]([^'\"]+)['\"]",
    r"url\s*\(\s*r?['\"]([^'\"]+)['\"]",
    r"register\s*\(\s*r?['\"]([^'\"]+)['\"]",
]

# Django/Python model patterns
PYTHON_MODEL_PATTERNS = [
    r"class\s+(\w+)\s*\(.*?models\.Model\)",
    r"class\s+(\w+)\s*\(.*?BaseModel\)",  # Pydantic
]

# NestJS entity/DTO patterns
NEST_MODEL_PATTERNS = [
    r"@Entity\s*\(.*?\)\s*(?:export\s+)?class\s+(\w+)",
    r"class\s+(\w+(?:Dto|DTO|Entity|Schema))\b",
]

# .NET model directory / naming hints (POCO, EF entity, VO/DO, etc.)
DOTNET_MODEL_DIR_HINTS = (
    "/model", "\\model", "/models", "\\models", "/domain", "\\domain",
    "/entit", "\\entit", "/dto", "\\dto", "/do/", "\\do\\", "/vo/", "\\vo\\",
)
DOTNET_SKIP_CLASS_SUFFIXES = ("Controller", "Service", "Program", "Startup", "Context", "Global")

# Android model directory / annotation hints
ANDROID_MODEL_DIR_HINTS = (
    "/model", "\\model", "/pojo", "\\pojo", "/bean", "\\bean",
    "/dto", "\\dto", "/vo/", "\\vo\\", "/entity", "\\entity", "/entities", "\\entities",
)
ANDROID_SKIP_CLASS_SUFFIXES = (
    "Activity", "Fragment", "Adapter", "Service", "Application",
    "Util", "Utils", "Helper", "Manager", "Receiver", "Provider",
)


def scan_project_markers(root: Path) -> Dict[str, List[Path]]:
    """Single-pass filesystem scan for stack-identifying marker files/dirs
    (.sln/.csproj, build.gradle, AndroidManifest.xml, .xcodeproj, Podfile, ...)."""
    markers: Dict[str, List[Path]] = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for dname in list(dirnames):
            if dname.endswith(".xcodeproj"):
                markers["xcodeproj"].append(Path(dirpath) / dname)
        for fname in filenames:
            suffix = Path(fname).suffix
            fpath = Path(dirpath) / fname
            if suffix == ".sln":
                markers["sln"].append(fpath)
            elif suffix == ".csproj":
                markers["csproj"].append(fpath)
            elif suffix == ".aspx":
                markers["aspx"].append(fpath)
            elif fname in ("build.gradle", "build.gradle.kts"):
                markers["gradle"].append(fpath)
            elif fname == "AndroidManifest.xml":
                markers["android_manifest"].append(fpath)
            elif fname == "project.pbxproj":
                markers["pbxproj"].append(fpath)
            elif fname == "Podfile":
                markers["podfile"].append(fpath)
            elif suffix == ".swift":
                markers["swift"].append(fpath)
            elif suffix == ".m":
                markers["objc_m"].append(fpath)
    return dict(markers)


def detect_framework(project_root: Path) -> Dict[str, Any]:
    """Detect framework from package.json (Node.js), project files (Python),
    or native-stack markers (.NET, Android, iOS)."""
    detected = []
    all_deps = {}
    pkg_name = ""
    pkg_version = ""

    # Node.js detection via package.json
    pkg_path = project_root / "package.json"
    if pkg_path.exists():
        try:
            with open(pkg_path) as f:
                pkg = json.load(f)
            pkg_name = pkg.get("name", "")
            pkg_version = pkg.get("version", "")
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                all_deps.update(pkg.get(key, {}))
            for framework, signals in FRAMEWORK_SIGNALS.items():
                if any(s in all_deps for s in signals):
                    detected.append(framework)
        except (json.JSONDecodeError, IOError):
            pass

    # Python backend detection via project files and imports
    if (project_root / "manage.py").exists():
        detected.append("django")
    if (project_root / "requirements.txt").exists() or (project_root / "pyproject.toml").exists():
        for req_file in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]:
            req_path = project_root / req_file
            if req_path.exists():
                try:
                    content = req_path.read_text(errors="replace").lower()
                    if "django" in content and "django" not in detected:
                        detected.append("django")
                    if "fastapi" in content:
                        detected.append("fastapi")
                    if "flask" in content and "flask" not in detected:
                        detected.append("flask")
                except IOError:
                    pass

    # Native stack detection via marker files (.NET, Android, iOS)
    markers = scan_project_markers(project_root)

    if markers.get("sln") or markers.get("csproj") or markers.get("aspx"):
        if markers.get("aspx"):
            detected.append("aspnet")
        else:
            detected.append("dotnet")

    if markers.get("gradle") and markers.get("android_manifest"):
        detected.append("android")

    if (markers.get("xcodeproj") or markers.get("pbxproj") or markers.get("podfile")
            or markers.get("swift") or markers.get("objc_m")):
        detected.append("ios")

    # Prefer specific over generic
    priority = [
        "android", "ios",                                 # native mobile
        "aspnet", "dotnet",                                # .NET / ASP.NET
        "sveltekit", "next", "nuxt", "remix", "astro",  # fullstack JS
        "nestjs", "express", "fastify",                   # backend JS
        "django", "fastapi", "flask",                     # backend Python
        "angular", "svelte", "vue", "react", "solid",     # frontend JS
    ]
    framework = "unknown"
    for fw in priority:
        if fw in detected:
            framework = fw
            break

    return {
        "framework": framework,
        "name": pkg_name or project_root.name,
        "version": pkg_version,
        "detected_frameworks": detected,
        "dependency_count": len(all_deps),
        "key_deps": {k: v for k, v in all_deps.items()
                     if any(s in k for s in ["router", "redux", "vuex", "pinia", "zustand",
                                              "mobx", "recoil", "jotai", "tanstack", "swr",
                                              "axios", "tailwind", "material", "ant",
                                              "chakra", "shadcn", "i18n", "intl",
                                              "typeorm", "prisma", "sequelize", "mongoose",
                                              "passport", "jwt", "class-validator"])},
    }


def find_dirs(root: Path, patterns: List[str]) -> List[Path]:
    """Find directories matching common patterns."""
    found = []
    for pattern in patterns:
        candidate = root / pattern
        if candidate.is_dir():
            found.append(candidate)
    return found


def walk_files(root: Path, extensions: Set[str] = CODE_EXTENSIONS) -> List[Path]:
    """Walk project tree, skip ignored dirs, return files matching extensions."""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for fname in filenames:
            if Path(fname).suffix in extensions:
                results.append(Path(dirpath) / fname)
    return results


def extract_routes_from_file(filepath: Path) -> List[Dict[str, str]]:
    """Extract route definitions from a file."""
    routes = []
    try:
        content = filepath.read_text(errors="replace")
    except IOError:
        return routes

    for pattern in ROUTE_PATTERNS:
        for match in re.finditer(pattern, content):
            path = match.group(1)
            if path and not path.startswith("http") and len(path) < 200:
                routes.append({
                    "path": path,
                    "source": str(filepath),
                    "line": content[:match.start()].count("\n") + 1,
                })
    return routes


def extract_routes_from_filesystem(pages_dir: Path, root: Path) -> List[Dict[str, str]]:
    """Infer routes from file-system routing (Next.js, Nuxt, SvelteKit)."""
    routes = []
    for filepath in sorted(pages_dir.rglob("*")):
        if filepath.is_file() and filepath.suffix in CODE_EXTENSIONS:
            rel = filepath.relative_to(pages_dir)
            route = "/" + str(rel.with_suffix("")).replace("\\", "/")
            # Normalize index routes
            route = re.sub(r"/index$", "", route) or "/"
            # Convert [param] to :param
            route = re.sub(r"\[\.\.\.(\w+)\]", r"*\1", route)
            route = re.sub(r"\[(\w+)\]", r":\1", route)
            routes.append({
                "path": route,
                "source": str(filepath),
                "filesystem": True,
            })
    return routes


def extract_android_apis(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract Android API calls: Retrofit @GET/@POST/... interface annotations,
    plus raw HttpURLConnection/OkHttp/Volley URL string literals."""
    apis: List[Dict[str, Any]] = []

    # Retrofit interface methods
    for match in re.finditer(r'@(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]*)"\s*\)', content):
        method = match.group(1)
        path = match.group(2)
        if not path.startswith("/"):
            path = "/" + path
        apis.append({
            "path": path,
            "method": method,
            "source": str(filepath),
            "line": content[:match.start()].count("\n") + 1,
            "integrated": True,
            "mock_detected": False,
        })

    # Raw URL literals (HttpURLConnection, OkHttp, Volley, etc.)
    for match in re.finditer(r'"(https?://[^"\s]+)"', content):
        path = match.group(1)
        if len(path) > 300:
            continue
        ctx = content[max(0, match.start() - 150):match.end() + 50]
        method = "UNKNOWN"
        for m in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            if re.search(rf"\b{m}\b", ctx):
                method = m
                break
        apis.append({
            "path": path,
            "method": method,
            "source": str(filepath),
            "line": content[:match.start()].count("\n") + 1,
            "integrated": True,
            "mock_detected": False,
        })
    return apis


def extract_ios_apis(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract iOS API calls: URLSession/Alamofire/AFNetworking + URL string literals
    (Swift `"..."` and Objective-C `@"..."`)."""
    apis: List[Dict[str, Any]] = []
    for match in re.finditer(r'@?"(https?://[^"\s]+)"', content):
        path = match.group(1)
        if len(path) > 300:
            continue
        ctx = content[max(0, match.start() - 150):match.end() + 80]
        method = "UNKNOWN"
        for m in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            if re.search(rf"\b{m}\b", ctx, re.IGNORECASE):
                method = m
                break
        apis.append({
            "path": path,
            "method": method,
            "source": str(filepath),
            "line": content[:match.start()].count("\n") + 1,
            "integrated": True,
            "mock_detected": False,
        })
    return apis


def extract_apis_from_file(filepath: Path) -> List[Dict[str, Any]]:
    """Extract API calls from a file. Dispatches to native-mobile extractors
    for Android/iOS source; falls through to the original axios/fetch/http
    heuristics for everything else."""
    try:
        content = filepath.read_text(errors="replace")
    except IOError:
        return []

    suffix = filepath.suffix
    if suffix in (".java", ".kt"):
        return extract_android_apis(filepath, content)
    if suffix in (".swift", ".m", ".h"):
        return extract_ios_apis(filepath, content)

    apis = []

    is_mock = any(re.search(p, content) for p in MOCK_SIGNALS)
    is_real = any(re.search(p, content) for p in REAL_API_SIGNALS)

    for pattern in API_PATH_PATTERNS:
        for match in re.finditer(pattern, content):
            path = match.group(1) if match.lastindex else match.group(0)
            if path and len(path) < 200:
                # Try to detect HTTP method
                context = content[max(0, match.start() - 100):match.end()]
                method = "UNKNOWN"
                for m in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    if m.lower() in context.lower():
                        method = m
                        break

                apis.append({
                    "path": path,
                    "method": method,
                    "source": str(filepath),
                    "line": content[:match.start()].count("\n") + 1,
                    "integrated": is_real and not is_mock,
                    "mock_detected": is_mock,
                })
    return apis


def extract_csharp_enums(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract C# enums, including members with no explicit value and
    [EnumMember(Value = "...")] string mappings (common in WCF DTOs)."""
    enums = []
    for match in re.finditer(r"enum\s+(\w+)\s*(?::\s*\w+)?\s*\{([^}]*)\}", content, re.DOTALL):
        name = match.group(1)
        body = match.group(2)
        values: Dict[str, str] = {}
        clean_body = re.sub(r"\[[^\]]*\]", "", body)
        for member in clean_body.split(","):
            member = member.strip()
            if not member:
                continue
            if "=" in member:
                k, v = member.split("=", 1)
                values[k.strip()] = v.strip()
            else:
                values[member] = ""
        # [EnumMember(Value = "Y")] SUCCESS, — maps member -> wire value
        for val, key in re.findall(r'\[EnumMember\s*\(\s*Value\s*=\s*"([^"]+)"\s*\)\]\s*([A-Za-z_]\w*)', body):
            values[key] = val
        enums.append({
            "name": name, "type": "enum", "values": values, "source": str(filepath),
        })
    return enums


def extract_java_kotlin_enums(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract Java/Kotlin enums, including constructor-arg members (e.g. PENDING("P"))."""
    enums = []
    for match in re.finditer(r"enum\s+(?:class\s+)?(\w+)\s*(?:\([^)]*\))?\s*\{([^}]*)\}", content, re.DOTALL):
        name = match.group(1)
        body = match.group(2)
        # Member list ends at the first `;` (start of methods/fields section), if present
        member_section = body.split(";")[0]
        values: Dict[str, str] = {}
        for member in member_section.split(","):
            member = member.strip()
            if not member:
                continue
            m2 = re.match(r"(\w+)(?:\(([^)]*)\))?", member)
            if m2:
                values[m2.group(1)] = (m2.group(2) or "").strip()
        if values:
            enums.append({
                "name": name, "type": "enum", "values": values, "source": str(filepath),
            })
    return enums


def extract_swift_objc_enums(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract Swift `enum ... { case ... }` and Objective-C `typedef NS_ENUM(...)`."""
    enums = []
    for match in re.finditer(r"enum\s+(\w+)\s*(?::\s*\w+)?\s*\{([^}]*)\}", content, re.DOTALL):
        name = match.group(1)
        body = match.group(2)
        values: Dict[str, str] = {}
        for cm in re.finditer(r"case\s+([^\n]+)", body):
            for part in cm.group(1).split(","):
                part = part.strip()
                if not part:
                    continue
                if "=" in part:
                    k, v = part.split("=", 1)
                    values[k.strip()] = v.strip()
                elif "(" in part:
                    values[part.split("(")[0].strip()] = ""
                else:
                    values[part] = ""
        if values:
            enums.append({
                "name": name, "type": "enum", "values": values, "source": str(filepath),
            })

    for match in re.finditer(r"typedef\s+NS_ENUM\s*\(\s*\w+\s*,\s*(\w+)\s*\)\s*\{([^}]*)\}", content, re.DOTALL):
        name = match.group(1)
        body = match.group(2)
        # Strip /* */ and // comments so they don't glue onto the following member name
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        body = re.sub(r"//[^\n]*", "", body)
        values = {}
        for member in body.split(","):
            member = member.strip()
            if not member:
                continue
            if "=" in member:
                k, v = member.split("=", 1)
                values[k.strip()] = v.strip()
            else:
                values[member] = ""
        enums.append({
            "name": name, "type": "enum", "values": values, "source": str(filepath),
        })
    return enums


def extract_enums(filepath: Path) -> List[Dict[str, Any]]:
    """Extract enum/constant definitions. Dispatches to stack-specific
    extractors for .NET/Android/iOS source; falls through to the original
    TypeScript/JS enum + constant-map heuristics for everything else."""
    try:
        content = filepath.read_text(errors="replace")
    except IOError:
        return []

    suffix = filepath.suffix
    if suffix == ".cs":
        return extract_csharp_enums(filepath, content)
    if suffix in (".java", ".kt"):
        return extract_java_kotlin_enums(filepath, content)
    if suffix in (".swift", ".m", ".h"):
        return extract_swift_objc_enums(filepath, content)

    enums = []

    # TypeScript enums
    for match in re.finditer(r"enum\s+(\w+)\s*\{([^}]+)\}", content):
        name = match.group(1)
        body = match.group(2)
        values = re.findall(r"(\w+)\s*=\s*['\"]?([^,'\"\n]+)", body)
        enums.append({
            "name": name,
            "type": "enum",
            "values": {k.strip(): v.strip().rstrip(",") for k, v in values},
            "source": str(filepath),
        })

    # Object constant maps (const STATUS_MAP = { ... })
    for match in re.finditer(
        r"(?:const|export\s+const)\s+(\w*(?:MAP|STATUS|TYPE|ENUM|OPTION|ROLE|STATE)\w*)\s*[:=]\s*\{([^}]+)\}",
        content, re.IGNORECASE
    ):
        name = match.group(1)
        body = match.group(2)
        values = re.findall(r"['\"]?(\w+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]", body)
        if values:
            enums.append({
                "name": name,
                "type": "constant_map",
                "values": dict(values),
                "source": str(filepath),
            })

    return enums


def extract_dotnet_backend_routes(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract .NET backend routes: WCF [ServiceContract]/[OperationContract]/[WebInvoke]/
    [WebGet] operations, and ASP.NET Web API/MVC [ApiController]/[Route]/[Http*] endpoints."""
    routes: List[Dict[str, Any]] = []

    # ---- WCF service operations ----
    if re.search(r"\[ServiceContract\]", content):
        for op_match in re.finditer(r"\[OperationContract\]", content):
            window = content[op_match.end():op_match.end() + 500]
            method = "POST"
            path: Optional[str] = None
            wi = re.search(r"\[WebInvoke\s*\(([^)]*)\)\]", window)
            wg = re.search(r"\[WebGet\s*(?:\(([^)]*)\))?\]", window)
            if wi:
                m = re.search(r'Method\s*=\s*"([^"]+)"', wi.group(1))
                u = re.search(r'UriTemplate\s*=\s*"([^"]+)"', wi.group(1))
                if m:
                    method = m.group(1).upper()
                if u:
                    path = u.group(1)
            elif wg:
                method = "GET"
                if wg.group(1):
                    u = re.search(r'UriTemplate\s*=\s*"([^"]+)"', wg.group(1))
                    if u:
                        path = u.group(1)
            sig = re.search(r"\b(\w+)\s*\(", window)
            op_name = sig.group(1) if sig else "Operation"
            if not path:
                path = op_name
            if not path.startswith("/"):
                path = "/" + path
            routes.append({
                "path": path,
                "method": method,
                "source": str(filepath),
                "line": content[:op_match.start()].count("\n") + 1,
                "type": "backend",
                "operation": op_name,
                "style": "wcf",
            })

    # ---- ASP.NET Web API / MVC controllers ----
    class_m = re.search(r"class\s+(\w*Controller)\b", content)
    if class_m and (
        "[ApiController]" in content
        or re.search(r"\[Route", content)
        or re.search(r"\[Http(Get|Post|Put|Delete|Patch)", content)
    ):
        controller_name = class_m.group(1)
        prefix = ""
        pre_class = content[:class_m.start()]
        route_matches = list(re.finditer(r'\[Route\s*\(\s*"([^"]*)"\s*\)\]', pre_class))
        if route_matches:
            prefix = route_matches[-1].group(1).replace(
                "[controller]", controller_name[:-len("Controller")] if controller_name.endswith("Controller") else controller_name
            )
        for m in re.finditer(r'\[Http(Get|Post|Put|Delete|Patch)\s*(?:\(\s*"([^"]*)"\s*\))?\]', content):
            method = m.group(1).upper()
            action_path = (m.group(2) or "").replace(
                "[controller]", controller_name[:-len("Controller")] if controller_name.endswith("Controller") else controller_name
            )
            if action_path.startswith("/"):
                full_path = action_path
            elif prefix:
                full_path = f"/{prefix.strip('/')}/{action_path}".rstrip("/") if action_path else f"/{prefix.strip('/')}"
            else:
                base = controller_name[:-len("Controller")] if controller_name.endswith("Controller") else controller_name
                full_path = f"/{base}/{action_path}".rstrip("/") if action_path else f"/{base}"
            full_path = re.sub(r"/{2,}", "/", full_path)

            ctx = content[max(0, m.start() - 200):m.start()]
            auth = "authorize" if "[Authorize" in ctx else ("anonymous" if "[AllowAnonymous" in ctx else None)

            entry = {
                "path": full_path,
                "method": method,
                "source": str(filepath),
                "line": content[:m.start()].count("\n") + 1,
                "type": "backend",
                "controller": controller_name,
                "style": "webapi",
            }
            if auth:
                entry["auth"] = auth
            routes.append(entry)

    return routes


def extract_backend_routes(filepath: Path, framework: str) -> List[Dict[str, str]]:
    """Extract route definitions from NestJS controllers, Django url configs, or .NET controllers/WCF services."""
    try:
        content = filepath.read_text(errors="replace")
    except IOError:
        return []

    if framework in ("dotnet", "aspnet"):
        return extract_dotnet_backend_routes(filepath, content)

    routes: List[Dict[str, str]] = []

    patterns = []
    if framework in ("nestjs", "express", "fastify"):
        patterns = NEST_ROUTE_PATTERNS
    elif framework == "django":
        patterns = DJANGO_ROUTE_PATTERNS

    # For NestJS, also grab the controller prefix
    controller_prefix = ""
    if framework == "nestjs":
        m = re.search(r"@Controller\s*\(\s*['\"]([^'\"]*)['\"]", content)
        if m:
            controller_prefix = "/" + m.group(1).strip("/")

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            path = match.group(1)
            if not path or path.startswith("http") or len(path) > 200:
                continue
            # For NestJS method decorators, prepend controller prefix
            if framework == "nestjs" and not path.startswith("/"):
                full_path = f"{controller_prefix}/{path}".replace("//", "/")
            else:
                full_path = path if path.startswith("/") else f"/{path}"

            # Detect HTTP method from decorator name
            method = "UNKNOWN"
            ctx = content[max(0, match.start() - 30):match.start()]
            for m_name in ["Get", "Post", "Put", "Delete", "Patch"]:
                if f"@{m_name}" in ctx or f"@{m_name.lower()}" in ctx:
                    method = m_name.upper()
                    break

            routes.append({
                "path": full_path,
                "method": method,
                "source": str(filepath),
                "line": content[:match.start()].count("\n") + 1,
                "type": "backend",
            })
    return routes


def extract_dotnet_models(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract .NET POCO/entity classes (Model/Domain/Entities/DTO/DO/VO dirs),
    EF DbContext DbSets, and data-annotation field constraints ([Required], [MaxLength], [Key])."""
    models: List[Dict[str, Any]] = []

    # EF DbContext
    for m in re.finditer(r"class\s+(\w+)\s*:\s*(?:[\w.]*\.)?DbContext\b", content):
        dbsets = re.findall(r"DbSet<(\w+)>\s+(\w+)", content)
        models.append({
            "name": m.group(1),
            "source": str(filepath),
            "framework": "dotnet",
            "type": "DbContext",
            "fields": [{"name": n, "type": f"DbSet<{t}>"} for t, n in dbsets],
        })

    path_str = str(filepath).lower()
    is_model_dir = any(h in path_str for h in DOTNET_MODEL_DIR_HINTS)
    has_annotation_hint = "[Key]" in content or "[Table(" in content or "[Required]" in content
    name_suffix_hint = re.search(r"class\s+\w+(?:VO|DO|DTO|Dto|Entity|Model)\b", content)

    if is_model_dir or has_annotation_hint or name_suffix_hint:
        for cm in re.finditer(r"(?:public\s+)?(?:partial\s+)?class\s+(\w+)\b[^{]*\{", content):
            cname = cm.group(1)
            if cname.endswith(DOTNET_SKIP_CLASS_SUFFIXES):
                continue
            block = content[cm.end():cm.end() + 3000]
            fields = []
            for fm in re.finditer(
                r"((?:\[[^\]]+\]\s*)*)\s*public\s+([\w<>\[\],\?]+)\s+(\w+)\s*\{\s*get;",
                block,
            ):
                attrs = fm.group(1)
                constraints = [
                    (f"{n}({a})" if a else n)
                    for n, a in re.findall(r"\[(\w+)(?:\(([^)]*)\))?\]", attrs)
                ]
                fields.append({
                    "name": fm.group(3),
                    "type": fm.group(2),
                    "constraints": constraints,
                })
            if fields or is_model_dir or name_suffix_hint:
                models.append({
                    "name": cname,
                    "source": str(filepath),
                    "framework": "dotnet",
                    "fields": fields,
                })
    return models


def extract_android_models(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract Android POJOs, Room @Entity classes, Gson-annotated classes, and Kotlin data classes."""
    models: List[Dict[str, Any]] = []
    path_str = str(filepath).lower()
    is_model_dir = any(h in path_str for h in ANDROID_MODEL_DIR_HINTS)
    is_entity = "@Entity" in content
    is_gson = "@SerializedName" in content

    if is_model_dir or is_entity or is_gson:
        for m in re.finditer(r"(?:public\s+)?(?:final\s+)?class\s+(\w+)\b[^{]*\{", content):
            name = m.group(1)
            if name.endswith(ANDROID_SKIP_CLASS_SUFFIXES):
                continue
            block = content[m.end():m.end() + 2000]
            fields = []
            for fm in re.finditer(
                r"(?:private|public|protected)\s+(?:final\s+)?([\w<>\[\],\.]+)\s+(\w+)\s*;", block
            ):
                fields.append({"type": fm.group(1).strip(), "name": fm.group(2)})
            models.append({
                "name": name,
                "source": str(filepath),
                "framework": "android",
                "fields": fields[:30],
            })

    # Kotlin data classes (explicit `data class`, low false-positive rate)
    for m in re.finditer(r"data\s+class\s+(\w+)\s*\(([^)]*)\)", content, re.DOTALL):
        name = m.group(1)
        params = m.group(2)
        fields = [
            {"name": n, "type": t}
            for n, t in re.findall(r"(?:val|var)\s+(\w+)\s*:\s*([\w<>\?\.]+)", params)
        ]
        models.append({
            "name": name,
            "source": str(filepath),
            "framework": "android",
            "fields": fields,
        })
    return models


def extract_ios_models(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract Swift struct/class models (Codable/named-model heuristics) and
    Objective-C @interface (NSObject) models with @property field lists."""
    models: List[Dict[str, Any]] = []

    # Swift struct/class
    for m in re.finditer(r"(?:struct|class)\s+(\w+)\s*:\s*([^{\n]*)\{", content):
        name = m.group(1)
        bases = m.group(2)
        if re.search(r"UIViewController|UITableViewController|UICollectionViewController", bases):
            continue
        is_struct = content[m.start():m.start() + 6].startswith("struct")
        is_codable = bool(re.search(r"Codable|Decodable|Encodable", bases))
        is_named_model = bool(re.search(r"(Model|VO|DTO|Response|Request|Entity)$", name))
        if not (is_struct or is_codable or is_named_model):
            continue
        block = content[m.end():m.end() + 2000]
        fields = [
            {"name": n, "type": t}
            for n, t in re.findall(r"(?:var|let)\s+(\w+)\s*:\s*([\w<>\[\]\?\.]+)", block)
        ][:30]
        models.append({
            "name": name,
            "source": str(filepath),
            "framework": "ios",
            "fields": fields,
        })

    # Objective-C @interface X : NSObject
    for m in re.finditer(r"@interface\s+(\w+)\s*:\s*(NSObject|NSManagedObject)\b", content):
        name = m.group(1)
        rest = content[m.end():]
        end_idx = rest.find("@end")
        block = rest[:end_idx] if end_idx != -1 else rest[:2000]
        fields = [
            {"name": fm.group(3), "type": fm.group(2).strip(), "attrs": fm.group(1).strip()}
            for fm in re.finditer(r"@property\s*\(([^)]*)\)\s*([\w<>\*\s]+?)\s*\*?\s*(\w+);", block)
        ]
        models.append({
            "name": name,
            "source": str(filepath),
            "framework": "ios",
            "fields": fields,
        })
    return models


def extract_models(filepath: Path, framework: str) -> List[Dict[str, Any]]:
    """Extract model/entity definitions from backend or native mobile code."""
    try:
        content = filepath.read_text(errors="replace")
    except IOError:
        return []

    suffix = filepath.suffix
    if suffix == ".cs":
        return extract_dotnet_models(filepath, content)
    if suffix in (".java", ".kt"):
        return extract_android_models(filepath, content)
    if suffix in (".swift", ".m", ".h"):
        return extract_ios_models(filepath, content)

    models = []
    patterns = PYTHON_MODEL_PATTERNS if framework in ("django", "fastapi", "flask") else NEST_MODEL_PATTERNS
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            name = match.group(1)
            # Try to extract fields
            fields = []
            # For Django models: field_name = models.FieldType(...)
            if framework == "django":
                block_start = match.end()
                block = content[block_start:block_start + 2000]
                for fm in re.finditer(
                    r"(\w+)\s*=\s*models\.(\w+)\s*\(([^)]*)\)", block
                ):
                    fields.append({
                        "name": fm.group(1),
                        "type": fm.group(2),
                        "args": fm.group(3).strip()[:100],
                    })
            models.append({
                "name": name,
                "source": str(filepath),
                "framework": framework,
                "fields": fields,
            })
    return models


def compute_stack_type(fw: str, backend_routes: List[Dict[str, Any]], frontend_routes: List[Dict[str, Any]]) -> str:
    """Classify the project's stack type. Preserves the original web-only logic
    (backend-only frameworks / fullstack / frontend) and adds `mobile` for
    native Android/iOS and `webforms` for ASP.NET Web Forms sites with no
    Web API/WCF backend routes."""
    if fw in ("android", "ios"):
        return "mobile"
    if fw == "aspnet":
        return "fullstack" if (backend_routes and frontend_routes) else "webforms"
    if fw in ("django", "fastapi", "flask", "nestjs", "express", "fastify", "dotnet") and not frontend_routes:
        return "backend"
    if backend_routes and frontend_routes:
        return "fullstack"
    return "frontend"


def count_components(files: List[Path]) -> Dict[str, int]:
    """Count components by type."""
    counts: Dict[str, int] = defaultdict(int)
    for f in files:
        if f.suffix in COMPONENT_EXTENSIONS:
            counts["components"] += 1
        elif f.suffix in {".ts", ".js"}:
            counts["modules"] += 1
    return dict(counts)


def extract_aspx_page(filepath: Path, content: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """One entry per ASP.NET Web Forms .aspx page, noting its code-behind class.
    Uses the path relative to the project root (not just the filename) so that
    same-named pages under different directories (e.g. Default.aspx in both
    Website/ and Admin/) don't collide during path-based dedup."""
    codebehind_m = re.search(r'CodeBehind\s*=\s*"([^"]+)"', content) or re.search(r'CodeFile\s*=\s*"([^"]+)"', content)
    inherits_m = re.search(r'Inherits\s*=\s*"([^"]+)"', content)
    if root is not None:
        try:
            rel = filepath.relative_to(root)
            path = "/" + str(rel).replace("\\", "/")
        except ValueError:
            path = "/" + filepath.name
    else:
        path = "/" + filepath.name
    return {
        "path": path,
        "source": str(filepath),
        "type": "webforms_page",
        "codebehind": codebehind_m.group(1) if codebehind_m else None,
        "class": inherits_m.group(1) if inherits_m else None,
    }


def extract_android_manifest_screens(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract <activity>/<fragment> declarations from AndroidManifest.xml."""
    screens = []
    for tag, label in (("activity", "android_activity"), ("fragment", "android_fragment")):
        for match in re.finditer(rf'<{tag}\b[^>]*android:name\s*=\s*"([^"]+)"', content):
            qualified = match.group(1)
            simple = qualified.split(".")[-1] if "." in qualified else qualified.lstrip(".")
            screens.append({
                "path": simple or qualified,
                "qualified_name": qualified,
                "source": str(filepath),
                "type": label,
                "line": content[:match.start()].count("\n") + 1,
            })
    return screens


def extract_android_class_screens(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract Activity/Fragment class declarations (Java `extends`, Kotlin `:`)."""
    screens = []
    for match in re.finditer(
        r"class\s+(\w+)\s*(?:extends|:)\s*([\w<>.]*(?:Activity|Fragment)[\w<>.]*)", content
    ):
        screens.append({
            "path": match.group(1),
            "source": str(filepath),
            "type": "android_screen",
            "base_class": match.group(2),
            "line": content[:match.start()].count("\n") + 1,
        })
    return screens


IOS_SCREEN_BASE_RE = r"UIViewController|UITableViewController|UICollectionViewController"


def extract_ios_class_screens(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract UIViewController subclasses (Swift `class X: ...` and Objective-C `@interface X : ...`),
    with @IBOutlet declarations attached as a rough field list."""
    screens = []
    outlets = extract_ios_outlets(content)
    for match in re.finditer(
        rf"class\s+(\w+)\s*:\s*([^{{\n]*?(?:{IOS_SCREEN_BASE_RE})[^{{\n]*)\{{", content
    ):
        screens.append({
            "path": match.group(1),
            "source": str(filepath),
            "type": "ios_screen",
            "base_class": match.group(2).strip(),
            "line": content[:match.start()].count("\n") + 1,
            "fields": outlets,
        })
    for match in re.finditer(
        rf"@interface\s+(\w+)\s*:\s*({IOS_SCREEN_BASE_RE})\b", content
    ):
        screens.append({
            "path": match.group(1),
            "source": str(filepath),
            "type": "ios_screen",
            "base_class": match.group(2),
            "line": content[:match.start()].count("\n") + 1,
            "fields": outlets,
        })
    return screens


def extract_ios_storyboard_scenes(filepath: Path, content: str) -> List[Dict[str, Any]]:
    """Extract storyboard/XIB scenes via their `customClass` attribute."""
    screens = []
    for match in re.finditer(r'customClass\s*=\s*"([^"]+)"', content):
        screens.append({
            "path": match.group(1),
            "source": str(filepath),
            "type": "ios_storyboard_scene",
            "line": content[:match.start()].count("\n") + 1,
        })
    return screens


def extract_ios_outlets(content: str) -> List[Dict[str, str]]:
    """Extract @IBOutlet field declarations (Objective-C @property and Swift var) — used as a rough field list."""
    outlets = []
    for m in re.finditer(r"@property\s*\([^)]*\)\s*IBOutlet\s+([\w<>\*\s]+?)\s*\*?\s*(\w+);", content):
        outlets.append({"name": m.group(2), "type": m.group(1).strip()})
    for m in re.finditer(r"@IBOutlet\s+(?:weak\s+|strong\s+)?var\s+(\w+)\s*:\s*([\w<>\?!]+)", content):
        outlets.append({"name": m.group(1), "type": m.group(2)})
    return outlets


def extract_screens(filepath: Path, framework: str, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Extract mobile/web-forms 'screens' — the non-URL equivalent of frontend pages:
    ASP.NET Web Forms .aspx pages, Android activities/fragments, iOS view controllers/scenes."""
    try:
        content = filepath.read_text(errors="replace")
    except IOError:
        return []

    if framework in ("dotnet", "aspnet") and filepath.suffix == ".aspx":
        return [extract_aspx_page(filepath, content, root)]
    if framework == "android":
        if filepath.name == "AndroidManifest.xml":
            return extract_android_manifest_screens(filepath, content)
        if filepath.suffix in (".java", ".kt"):
            return extract_android_class_screens(filepath, content)
    if framework == "ios":
        if filepath.suffix in (".swift", ".m", ".h"):
            return extract_ios_class_screens(filepath, content)
        if filepath.suffix in (".storyboard", ".xib"):
            return extract_ios_storyboard_scenes(filepath, content)
    return []


def analyze_project(project_root: Path) -> Dict[str, Any]:
    """Run full analysis on a frontend project."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {root}"}

    # 1. Framework detection
    framework_info = detect_framework(root)

    # 2. File inventory
    all_files = walk_files(root)
    component_counts = count_components(all_files)

    # 3. Directory structure
    route_dirs = find_dirs(root, ROUTE_DIR_PATTERNS)
    api_dirs = find_dirs(root, API_DIR_PATTERNS)
    state_dirs = find_dirs(root, STATE_DIR_PATTERNS)
    i18n_dirs = find_dirs(root, I18N_DIR_PATTERNS)

    # 4. Routes (frontend + backend)
    routes = []
    fw = framework_info["framework"]

    # Frontend: config-based routes
    for f in all_files:
        if any(p in f.name.lower() for p in ["router", "routes", "routing"]):
            routes.extend(extract_routes_from_file(f))

    # Frontend: file-system routes (Next.js, Nuxt, SvelteKit)
    if fw in ("next", "nuxt", "sveltekit", "remix", "astro"):
        for d in route_dirs:
            routes.extend(extract_routes_from_filesystem(d, root))

    # Backend: NestJS controllers, Django urls, .NET Web API/MVC controllers + WCF services
    if fw in ("nestjs", "express", "fastify", "django", "dotnet", "aspnet"):
        for f in all_files:
            if fw == "django" and "urls.py" in f.name:
                routes.extend(extract_backend_routes(f, fw))
            elif fw in ("nestjs", "express", "fastify") and ".controller." in f.name:
                routes.extend(extract_backend_routes(f, fw))
            elif fw in ("dotnet", "aspnet") and f.suffix == ".cs":
                routes.extend(extract_backend_routes(f, fw))

    # Screens: ASP.NET Web Forms .aspx pages, Android activities/fragments, iOS view controllers/scenes
    if fw in ("dotnet", "aspnet"):
        for f in all_files:
            if f.suffix == ".aspx":
                routes.extend(extract_screens(f, fw, root))
    elif fw == "android":
        for f in all_files:
            if f.name == "AndroidManifest.xml" or f.suffix in (".java", ".kt"):
                routes.extend(extract_screens(f, fw, root))
    elif fw == "ios":
        for f in all_files:
            if f.suffix in (".swift", ".m", ".h", ".storyboard", ".xib"):
                routes.extend(extract_screens(f, fw, root))

    # Deduplicate routes by path (+ method for backend)
    seen_paths: Set[str] = set()
    unique_routes = []
    for r in routes:
        key = r["path"] if r.get("type") != "backend" else f"{r.get('method', '')}:{r['path']}"
        if key not in seen_paths:
            seen_paths.add(key)
            unique_routes.append(r)
    routes = sorted(unique_routes, key=lambda r: r["path"])

    # 5. API calls
    apis = []
    for f in all_files:
        apis.extend(extract_apis_from_file(f))

    # Deduplicate APIs by path+method
    seen_apis: Set[Tuple[str, str]] = set()
    unique_apis = []
    for a in apis:
        key = (a["path"], a["method"])
        if key not in seen_apis:
            seen_apis.add(key)
            unique_apis.append(a)
    apis = sorted(unique_apis, key=lambda a: a["path"])

    # 6. Enums
    enums = []
    for f in all_files:
        enums.extend(extract_enums(f))

    # 7. Models/entities (backend + native mobile)
    models = []
    if fw in ("django", "fastapi", "flask", "nestjs"):
        for f in all_files:
            if fw == "django" and "models.py" in f.name:
                models.extend(extract_models(f, fw))
            elif fw == "nestjs" and (".entity." in f.name or ".dto." in f.name):
                models.extend(extract_models(f, fw))
    elif fw in ("dotnet", "aspnet"):
        for f in all_files:
            if f.suffix == ".cs":
                models.extend(extract_models(f, fw))
    elif fw == "android":
        for f in all_files:
            if f.suffix in (".java", ".kt"):
                models.extend(extract_models(f, fw))
    elif fw == "ios":
        for f in all_files:
            if f.suffix in (".swift", ".m", ".h"):
                models.extend(extract_models(f, fw))

    # Deduplicate models by name
    seen_models: Set[str] = set()
    unique_models = []
    for m in models:
        if m["name"] not in seen_models:
            seen_models.add(m["name"])
            unique_models.append(m)
    models = sorted(unique_models, key=lambda m: m["name"])

    # Backend-specific directories
    controller_dirs = find_dirs(root, CONTROLLER_DIR_PATTERNS)
    model_dirs = find_dirs(root, MODEL_DIR_PATTERNS)
    dto_dirs = find_dirs(root, DTO_DIR_PATTERNS)

    # 8. Summary
    mock_count = sum(1 for a in apis if a.get("mock_detected"))
    real_count = sum(1 for a in apis if a.get("integrated"))
    backend_routes = [r for r in routes if r.get("type") == "backend"]
    frontend_routes = [r for r in routes if r.get("type") != "backend"]
    stack_type = compute_stack_type(fw, backend_routes, frontend_routes)

    analysis = {
        "project": {
            "root": str(root),
            "name": framework_info.get("name", root.name),
            "framework": framework_info["framework"],
            "detected_frameworks": framework_info.get("detected_frameworks", []),
            "key_dependencies": framework_info.get("key_deps", {}),
            "stack_type": stack_type,
        },
        "structure": {
            "total_files": len(all_files),
            "components": component_counts,
            "route_dirs": [str(d) for d in route_dirs],
            "api_dirs": [str(d) for d in api_dirs],
            "state_dirs": [str(d) for d in state_dirs],
            "i18n_dirs": [str(d) for d in i18n_dirs],
            "controller_dirs": [str(d) for d in controller_dirs],
            "model_dirs": [str(d) for d in model_dirs],
            "dto_dirs": [str(d) for d in dto_dirs],
        },
        "routes": {
            "count": len(routes),
            "frontend_pages": frontend_routes,
            "backend_endpoints": backend_routes,
            "pages": routes,  # backward compat
        },
        "apis": {
            "total": len(apis),
            "integrated": real_count,
            "mock": mock_count,
            "endpoints": apis,
        },
        "enums": {
            "count": len(enums),
            "definitions": enums,
        },
        "models": {
            "count": len(models),
            "definitions": models,
        },
        "summary": {
            "pages": len(frontend_routes),
            "backend_endpoints": len(backend_routes),
            "api_endpoints": len(apis),
            "api_integrated": real_count,
            "api_mock": mock_count,
            "enums": len(enums),
            "models": len(models),
            "has_i18n": len(i18n_dirs) > 0,
            "has_state_management": len(state_dirs) > 0,
            "stack_type": stack_type,
        },
    }

    return analysis


def format_markdown(analysis: Dict[str, Any]) -> str:
    """Format analysis as markdown summary."""
    lines = []
    proj = analysis["project"]
    summary = analysis["summary"]
    stack = summary.get("stack_type", "frontend")

    lines.append(f"# Codebase Analysis: {proj['name'] or 'Project'}")
    lines.append("")
    lines.append(f"**Framework:** {proj['framework']}")
    lines.append(f"**Stack type:** {stack}")
    lines.append(f"**Total files:** {analysis['structure']['total_files']}")
    if summary.get("pages"):
        lines.append(f"**Frontend pages:** {summary['pages']}")
    if summary.get("backend_endpoints"):
        lines.append(f"**Backend endpoints:** {summary['backend_endpoints']}")
    lines.append(f"**API calls detected:** {summary['api_endpoints']} "
                 f"({summary['api_integrated']} integrated, {summary['api_mock']} mock)")
    lines.append(f"**Enums:** {summary['enums']}")
    if summary.get("models"):
        lines.append(f"**Models/entities:** {summary['models']}")
    lines.append(f"**i18n:** {'Yes' if summary['has_i18n'] else 'No'}")
    lines.append(f"**State management:** {'Yes' if summary['has_state_management'] else 'No'}")
    lines.append("")

    if analysis["routes"]["pages"]:
        lines.append("## Pages / Routes")
        lines.append("")
        lines.append("| # | Route | Source |")
        lines.append("|---|-------|--------|")
        for i, r in enumerate(analysis["routes"]["pages"], 1):
            src = r.get("source", "").split("/")[-1]
            fs = " (fs)" if r.get("filesystem") else ""
            lines.append(f"| {i} | `{r['path']}` | {src}{fs} |")
        lines.append("")

    if analysis["apis"]["endpoints"]:
        lines.append("## API Endpoints")
        lines.append("")
        lines.append("| Method | Path | Integrated | Source |")
        lines.append("|--------|------|-----------|--------|")
        for a in analysis["apis"]["endpoints"]:
            src = a.get("source", "").split("/")[-1]
            status = "✅" if a.get("integrated") else "⚠️ Mock"
            lines.append(f"| {a['method']} | `{a['path']}` | {status} | {src} |")
        lines.append("")

    if analysis["enums"]["definitions"]:
        lines.append("## Enums & Constants")
        lines.append("")
        for e in analysis["enums"]["definitions"]:
            lines.append(f"### {e['name']} ({e['type']})")
            if e["values"]:
                lines.append("| Key | Value |")
                lines.append("|-----|-------|")
                for k, v in e["values"].items():
                    lines.append(f"| {k} | {v} |")
            lines.append("")

    if analysis.get("models", {}).get("definitions"):
        lines.append("## Models / Entities")
        lines.append("")
        for m in analysis["models"]["definitions"]:
            lines.append(f"### {m['name']} ({m.get('framework', '')})")
            if m.get("fields"):
                lines.append("| Field | Type | Args |")
                lines.append("|-------|------|------|")
                for fld in m["fields"]:
                    lines.append(f"| {fld['name']} | {fld['type']} | {fld.get('args', '')} |")
            lines.append("")

    if proj.get("key_dependencies"):
        lines.append("## Key Dependencies")
        lines.append("")
        for dep, ver in sorted(proj["key_dependencies"].items()):
            lines.append(f"- `{dep}`: {ver}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze any codebase (frontend, backend, fullstack) for PRD generation"
    )
    parser.add_argument("project", help="Path to project root")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument(
        "-f", "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    analysis = analyze_project(Path(args.project))

    if args.format == "markdown":
        output = format_markdown(analysis)
    else:
        output = json.dumps(analysis, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
