import abc


class MediaStorageInterface(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get(self, file_path):
        pass

    @abc.abstractmethod
    def put(self, content, file_path):
        pass

    @abc.abstractmethod
    def url_for_media(self, project_id):
        pass

    @abc.abstractmethod
    def delete(self, file_path):
        pass
