import re
from config import G3Config

def C(key):
    return G3Config.COMMENTS.get(key, f"[Missing config entry: {key}]")

def check_g3(req_text, hardware):
    t = req_text.lower()
    comments = []

    # ================= G3.1 =================
    g31 = "Yes"

    if "external memory" in t and not hardware["external_memory"]:
        g31 = "No"
        comments.append(C("g31_hw_assumption"))

    freq = re.search(r"(\d+)\s*khz", t)
    if freq and int(freq.group(1)) > hardware["cpu_mhz"] * 10:
        g31 = "No"
        comments.append(C("g31_cpu_load"))

    if g31 == "Yes" and "cpu" in t:
        comments.append(C("g31_not_justified"))

    # ================= G3.2 =================
    g32 = "Yes"

    if not any(k in t for k in G3Config.TIMING_KEYWORDS):
        g32 = "No"
        comments.append(C("g32_no_timing"))

    # ================= G3.3 =================
    g33 = "Yes"

    for iface in G3Config.UNSUPPORTED_INTERFACES:
        if iface in t:
            g33 = "No"
            comments.append(C("g33_unsupported_iface").format(iface.upper()))
            break

    if g33 == "Yes" and any(i in t for i in G3Config.SUPPORTED_INTERFACES) and "rate" not in t:
        comments.append(C("g33_no_bandwidth"))

    # ================= G3.4 =================
    g34 = "Yes"

    if "dynamic memory" in t or "malloc" in t:
        g34 = "No"
        comments.append(C("g34_dynamic_memory"))

    elif "continuous" in t or "unbounded" in t:
        g34 = "No"
        comments.append(C("g34_unbounded"))

    elif "buffer" in t and "size" not in t:
        comments.append(C("g34_resource_size"))

    return g31, g32, g33, g34, "; ".join(comments)
#hi rahul