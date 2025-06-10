import pickle
import bpy


#
# Render preparations
#

# Load the prepared .blend file
bpy.ops.wm.open_mainfile(filepath="canvas.blend")

# Verify/Set render output to video (if not already configured in the .blend file)
bpy.context.scene.render.image_settings.file_format = 'FFMPEG'
bpy.context.scene.render.ffmpeg.format = 'MPEG4'  # H.264 MP4
bpy.context.scene.render.filepath = "wordticker.mp4"

lane_spacing = 1.5
fps = bpy.data.scenes["Scene"].render.fps

#
# Init
#

# Create or retrieve the shared material
if "word_material" not in bpy.data.materials:
    mat = bpy.data.materials.new(name="word_material")
    mat.use_nodes = True  # Enable node editing for future customization
else:
    mat = bpy.data.materials["word_material"]

# Load data, create objects
with open("ticker.pickle", "rb") as file:
    ticker = pickle.load(file)

for lane_idx, lane in enumerate(ticker.lanes):
    y_loc = lane_idx * lane_spacing
    
    for appearance in lane:

        # Create the text object
        bpy.ops.object.text_add(location=(0, y_loc, 0))
        text_obj = bpy.context.object
        text_obj.data.body = appearance.term

        text_obj.name = f"{appearance.apid}"
        text_obj["value"] = 0.0
    
        if text_obj.data.materials:
            text_obj.data.materials[0] = mat
        else:
            text_obj.data.materials.append(mat)

#
# Update upon frame change
#

def update_values(scene):
    current_frame = scene.frame_current
    for obj in bpy.data.objects:
        if "value" in obj:
            t = current_frame / fps
            val = ticker.get_value(obj.name, t)  # You implement this
            obj["value"] = val
            obj.location.x = obj["value"] * (-22)

#bpy.app.handlers.frame_change_post.clear()  # Clear existing handlers if needed
bpy.app.handlers.frame_change_post.append(update_values)

#
# Render the animation
#
bpy.ops.render.render(animation=True)
#bpy.ops.wm.save_as_mainfile(filepath="canvas_filled.blend")

