import os,re
def _authorized():
 try:
  from com.alvsia.pro.sec import SessionGate
  return bool(SessionGate.isSessionAuthorized())
 except Exception:return False
def _isr():
 if os.environ.get("ALVSIA_SEALED_RUNTIME")!="1" or not _authorized():return
 try:
  import pkgutil
  if pkgutil.get_data("sealed","alvsia_bridge_impl.alv"):
   import sealed_loader
   sealed_loader.install()
 except Exception:pass
_CD=""
def configure_diagnostic():return _CD
def configure_unluac_rs(binary_path):
 try:
  path=os.path.realpath(_extract_str(binary_path).strip())
  if not os.path.isfile(path) or not os.access(path,os.X_OK):
   os.environ.pop("ALVSIA_UNLUAC_RS_BIN",None);return False
  os.environ["ALVSIA_UNLUAC_RS_BIN"]=path
  return True
 except Exception:
  os.environ.pop("ALVSIA_UNLUAC_RS_BIN",None);return False
def _extract_str(v):
 if isinstance(v,str):return v
 try:return str(v.toString())
 except Exception:return str(v)
def configure_runtime(token,sealed_runtime="1"):
 global _CD
 try:
  token=_extract_str(token).strip()
  if not re.fullmatch(r"[0-9A-Fa-f]{64}",token):_CD="error";return False
  from com.alvsia.pro.sec import SessionGate as gate
  if not bool(gate.isTokenCurrent(token)):_CD="error";return False
  os.environ.pop("ALVSIA_SESSION_TOKEN",None)
  os.environ["ALVSIA_APK_SESSION"]="1"
  os.environ["ALVSIA_SEALED_RUNTIME"]="1" if _extract_str(sealed_runtime).strip()=="1" else "0"
  _isr();_CD="ok";return True
 except Exception:
  # Release-safe diagnostic: never return internal stage, module, or exception details.
  _CD="error"
  return False
def run_tool(mid,sid,inp,out_root,engine_dir,jars_dir):
 if not _authorized() or os.environ.get("ALVSIA_APK_SESSION")!="1":return "X AUTH: login required"
 _isr()
 try:
  import alvsia_bridge_impl as impl
  result=impl.run_tool(mid,sid,inp,out_root,engine_dir,jars_dir)
  try:
   from alvsia_features import scrub_foreign_branding, scrub_output_text_files
   result,_=scrub_foreign_branding(result)
   scrub_output_text_files(out_root)
  except Exception:pass
  return result
 except Exception:
  return "X SEALED BRIDGE: operation failed"
def bridge_run_sub(mid,sid,inp,en,wd,jd):
 return run_tool(int(mid),str(sid),str(inp) if inp else "",str(wd),str(jd),str(jd))
