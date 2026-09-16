import json,os,sys,types
COMFY=r"E:\code\ComfyUI"
sys.path.insert(0,COMFY)
fp=types.ModuleType("folder_paths"); fp.get_input_directory=lambda: os.path.join(COMFY,"input"); fp.get_output_directory=lambda: os.path.join(COMFY,"output")
sys.modules["folder_paths"]=fp
sys.path.insert(0,os.path.join(COMFY,"custom_nodes"))
from comfyui_media_audit.nodes import InsightFaceFeature
n=InsightFaceFeature()
for p in [r"OUTPUT\01_paper_plane\frames\05_zhang_shuyang_catches_plane_00004_.png", r"ASSETS\CHARACTERS\_group\four_students_hero_v02.png"]:
    out,_=n.extract(os.path.abspath(p),"buffalo_l","CPU",640,0.3,True,512,4)
    d=json.loads(out)
    print(os.path.basename(p),'ok=',d.get('ok'),'err=',str(d.get('error'))[:200])
    if d.get('ok'):
        im=d['images'][0]; print('   faces',im['face_count'],'h',im['faces'][0]['face_px_h'] if im['face_count'] else None,'reembed',im['faces'][0].get('reembed_crop_px') if im['face_count'] else None)
