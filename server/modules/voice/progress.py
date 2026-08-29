class VoiceProgressTracker:
    def __init__(self):
        self.phase = None
        self.spoken_phases = set()

    def reset(self):
        self.phase = None
        self.spoken_phases.clear()

    def update(self, phase):
        if phase == self.phase:
            return None

        self.phase = phase

        if phase in self.spoken_phases:
            return None

        self.spoken_phases.add(phase)

        return self._message_for(phase)

    def _message_for(self, phase):

        messages = {
            "document_search": "I'm checking your documents first.",
            "web_search": "I'm cross-checking that with the web.",
            "verification": "I'm rechecking the information before I answer.",
            "answer": None,
        }

        return messages.get(phase)
