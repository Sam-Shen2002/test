class LogHook:
    def __init__(self, log_entry_id, update_func):
        self.log_entry_id = log_entry_id
        self.update_func = update_func

    def write(self, message):
        if 'parsing finished' in message.lower():
            self.update_func(self.log_entry_id, 100, 'Process Completed')
        elif 'extracting' in message.lower():
            self.update_func(self.log_entry_id, 10, 'Extracting')
        elif 'merging' in message.lower():
            self.update_func(self.log_entry_id, 40, 'Merging Logs')
        elif 'startcode' in message.lower():
            self.update_func(self.log_entry_id, 60, 'Parsing Startcode')
        elif 'saving result' in message.lower():
            self.update_func(self.log_entry_id, 90, 'Saving Results')

    def flush(self):  # for compatibility
        pass
