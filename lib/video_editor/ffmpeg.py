import json
import os
import subprocess
import logging

from lib.utils import create_file_name, create_temp_file

from .interface import VideoEditorInterface

logger = logging.getLogger(__name__)


class FFMPEGVideoEditor(VideoEditorInterface):
    """
    FFMPEG based video editor
    """

    def get_meta(self, filestream, extension='tmp'):
        """
        Use ffmpeg tool for getting metadata of video file
        :param filestream:
        :return:
        """
        file_name = create_file_name(extension)
        file_temp_path = create_temp_file(filestream, file_name)
        try:
            metadata = self._get_meta(file_temp_path)
        finally:
            os.remove(file_temp_path)

        return metadata

    def edit_video(self, stream_file, filename, metadata, video_cut=None, video_crop=None, video_rotate=None,
                   video_quality=None):
        """
        Use ffmpeg tool for edit video
        :param stream_file:
        :param filename:
        :param metadata:
        :param video_cut:
        :param video_crop:
        :param video_rotate:
        :param video_quality:
        :return:
        """
        path_video = ''
        try:
            path_video = create_temp_file(stream_file, filename)

            if not metadata:
                metadata = self._get_meta(path_video)

            duration = float(metadata['duration'])
            if (not video_cut or (video_cut['start'] == 0 and int(video_cut['end']) == int(duration))) \
                    and not video_crop \
                    and (not video_rotate or int(video_rotate['degree']) % 360 == 0) \
                    and not video_quality:
                return None, {}
            path_output = path_video + "_edit" + os.path.splitext(filename)[1]
            # use copy data
            # set option and run cut first
            if video_cut:
                path_video = self._edit_video(path_video, path_output,
                                              ["-ss", str(video_cut["start"]), "-t",
                                               str(int(video_cut["end"]) - int(video_cut["start"])), "-c", "copy"])

            # use filter data
            str_filter = ""
            # set option for crop
            if video_crop:
                # get max width, height if crop over the video
                if int(video_crop.get('width')) > int(metadata.get('width')):
                    video_crop['width'] = int(metadata.get('width'))
                if int(video_crop.get('height')) > int(metadata.get('height')):
                    video_crop['height'] = int(metadata.get('height'))
                str_filter += "crop=%s:%s:%s:%s" % (
                    video_crop["width"], video_crop["height"], video_crop["x"], video_crop["y"])
            # set option for rotate
            if video_rotate:
                delta90 = round((int(video_rotate['degree'] % 360) / 90))
                if delta90 != 0:
                    rotate_string = ''
                    if delta90 == 1:
                        rotate_string = "transpose=1"
                    if delta90 == 2:
                        rotate_string = "transpose=2,transpose=2"
                    if delta90 == 3:
                        rotate_string = "transpose=2"
                    str_filter += "," if str_filter != "" else ''
                    str_filter += rotate_string
            # set option for quality
            if video_quality:
                str_filter += "," if str_filter != "" else ''
                str_filter += "scale=%s:-2" % video_quality['quality']
            if str_filter != '':
                path_video = self._edit_video(path_video, path_output,
                                              ["-filter:v", str_filter, "-max_muxing_queue_size", "1024", "-threads",
                                               "5", "-preset", "ultrafast", "-strict", "-2", "-c:a", "copy"
                                               ])
            content = open(path_video, "rb+").read()
            metadata_edit_file = self._get_meta(path_video)
        finally:
            if path_video:
                os.remove(path_video)
        return content, metadata_edit_file

    def capture_thumbnail(self, stream_file, filename, duration, position):
        """
        Use ffmpeg tool to capture video frame at a position.
        :param stream_file: binary file stream
        :param filename: video's file name
        :param duration: video's duration
        :param position: video position to capture a frame
        :return: file stream, metadata
        """

        path_video = create_temp_file(stream_file, filename)
        try:
            # avoid the last frame, it is null
            if int(duration) <= int(position):
                position = duration - 0.1
            # create output file path
            output_file = f"{path_video}_preview_thumbnail.png"
            # run ffmpeg command
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-accurate_seek", "-i", path_video,
                            "-ss", str(position), "-vframes", "1", output_file])
            try:
                # get metadata
                thumbnail_metadata = self._get_meta(output_file)
                thumbnail_metadata['mimetype'] = 'image/png'
                # read binary
                with open(output_file, "rb") as f:
                    content = f.read()
                return content, thumbnail_metadata
            finally:
                # delete temp thumbnail file
                os.remove(output_file)
        finally:
            os.remove(path_video)

    def capture_timeline_thumbnails(self, stream_file, filename, duration, thumbnails_amount):
        """
        Capture thumbnails for timeline.
        :param stream_file: binary file stream
        :param filename: video's file name
        :param duration: video's duration
        :param thumbnails_amount: total number of thumbnails to capture
        :return: file stream, metadata generator
        """

        path_video = create_temp_file(stream_file, filename)
        try:
            # time period between two frames
            if thumbnails_amount == 1:
                frame_per_second = (duration - 1)
            else:
                frame_per_second = (duration - 1) / (thumbnails_amount - 1)

            # capture list frame via script capture_list_frames.sh
            path_script = os.path.dirname(__file__) + '/script/capture_list_frames.sh'
            # create output file path
            output_file = f"{path_video}_"
            # subprocess bash -> ffmpeg in the loop
            subprocess.run([path_script, path_video, output_file, str(frame_per_second), str(thumbnails_amount)])
            for i in range(0, thumbnails_amount):
                thumbnail_path =  f'{output_file}{i}.png'
                try:
                    # get metadata
                    thumbnail_metadata = self._get_meta(thumbnail_path)
                    thumbnail_metadata['mimetype'] = 'image/png'
                    # read binary
                    with open(thumbnail_path, "rb") as f:
                        content = f.read()
                    yield content, thumbnail_metadata
                finally:
                    # delete temp thumbnail file
                    os.remove(thumbnail_path)
        finally:
            os.remove(path_video)

    def _edit_video(self, path_video, path_output, para=[]):
        """
             Use ffmpeg to cutting video via start time and end time, and get the total frames of video.
        :param path_video:
        :param path_output:
        :param para:
        :return:
        """
        try:
            # cut video
            subprocess.run(["ffmpeg", "-v", "error", "-i", path_video, *para, path_output])

            # replace tmp origin

            subprocess.run(["cp", "-r", path_output, path_video])
            return path_video
        finally:
            os.remove(path_output)

    def _get_meta(self, file_path):
        """
        Get metada using `ffprobe` command
        :param file_path: path to a file to retrieve a metadata
        :return:
        """

        cmd = ('ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', file_path)
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            (output, _) = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"Subprocess with command: '{cmd}' has failed.")

        video_data = json.loads(output.decode("utf-8"))

        data = None
        for stream in video_data['streams']:
            if stream['codec_type'] == 'video':
                data = stream
                break

        video_meta_keys = ('codec_name', 'codec_long_name', 'width', 'height', 'r_frame_rate', 'bit_rate',
                           'nb_frames', 'duration')

        metadata = {key: data.get(key) for key in video_meta_keys}
        metadata['format_name'] = video_data['format']['format_name']
        metadata['size'] = video_data['format']['size']

        # some videos don't have duration in video stream
        if not metadata['duration']:
            metadata['duration'] = video_data['format'].get('duration')

        # ffmpeg output some number type as string
        format_type = {
            'size': int,
            'bit_rate': int,
            'nb_frames': int,
            'duration': float,
        }
        for value in format_type:
            if metadata.get(value):
                metadata[value] = format_type[value](metadata[value])

        return metadata
