__author__ = 'sean.mcgrath'
import csv, re, os, email, logging, shutil
logging.basicConfig(filename='log.log', filemode='w+', level=logging.DEBUG)

# Share name to strip from the beginning of each path in Newforma output
# Jesus Backslash Christ, that's 4 backslashes per backslash
SHARE_NAME = '\\\\\\\\ahg-sto-100\\\\nf\\\\'
SHARE_REGEX = re.compile('^' + SHARE_NAME, re.IGNORECASE)
SUBJECT_REGEX = re.compile('^Subject: (.+)$')

# Path to files on current system
EMAIL_PATH = '/akl_live/newforma_pm/'
MOVE_TARGET_PATH = '/akl_live/akl_office/data/hcg/hr/admin/SensitiveEmails/'

FILE_TOTAL_COUNTER = 0
FILE_READ_COUNTER = 0

class Directory:

    def __init__(self, path):
        self.original_path = path
        self.relative_path = self.clean_path(path)
        self.current_path = EMAIL_PATH + self.relative_path
        self.move_path = MOVE_TARGET_PATH + self.relative_path
        self.subjects = []

    def __repr__(self):
        return self.original_path

    def print_current_path(self):
        return self.current_path

    def clean_path(self, path):
        path = re.sub(SHARE_REGEX, '', path)
        path = re.sub('\\\\', '/', path)
        return self.fix_illegal_path(path)

    def fix_illegal_path(self, path):
        path = re.sub('_2X68Q~7', ' ', path)
        path = re.sub('N7FNV4~6', 'N.D.M.', path)
        path = re.sub('CPFVGE~0', 'CPeng ', path)
        return path

    def clean_subject(self, subject):
        return re.sub(' \[.*\]', '', subject)

    def add_subject(self, original_subject):
        clean_subj = self.clean_subject(original_subject)
        subject = next((subj for subj in self.subjects if subj.subject == clean_subj), None)
        if not subject:
            self.subjects.append(Subject(clean_subj))


class Subject:
    def __init__(self, original_subject):
        self.subject = original_subject
        self.files = []
        self.questionable_files = []

    def __repr__(self):
        return self.subject

    def add_file(self, file):
        if file not in self.files:
            self.files.append(file)

    # These are files which we didn't match the subject on, but match subject vs filename
    def add_questionable_file(self, file):
        if file not in self.files:
            if file not in self.questionable_files:
                self.questionable_files.append(file)
        else:
            logging.error('Attempted to add to questionable files but already matched: {}'.format(file))


def walklevel(dir, level=1):
    dir = dir.rstrip(os.path.sep)
    assert os.path.isdir(dir)
    num_sep = dir.count(os.path.sep)
    for root, dirs, files in os.walk(dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]

def build_dir_list():
    dir_list = []
    with open('list.csv', encoding='latin-1', newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in csvreader:
            directory = next((dir for dir in dir_list if dir.__repr__() == row[0]), None)
            if not directory:
                directory = Directory(row[0])
                dir_list.append(directory)
            directory.add_subject(row[1])
    return dir_list

def match_files(dir):
    for file in next(walklevel(dir.current_path))[2]:
        count()
        if 'no subject' not in file:
            read_count()
            file_path = dir.current_path + '/' +  file
            file_subject = fast_interpret(file_path)
            if file_subject:
                for subject in dir.subjects:
                    if file_subject == subject.subject:
                        subject.add_file(file)
                    elif subject.subject in file:
                        subject.add_questionable_file(file)


def fast_interpret(file):
    with open(file) as f:
        for lineno, line in enumerate(f, 1):
            if lineno > 100:
                return slow_interpret(file)
            else:
                m = SUBJECT_REGEX.match(line)
                if m:
                    if len(m.group(1)) > 1:
                        return m.group(1)
                    else:
                        return slow_interpret(file)
        return slow_interpret(file)


def slow_interpret(file):
    with open (file) as f:
        msg = email.message_from_file(f)
    try:
        subject, encoding = email.header.decode_header(msg.get('Subject'))[0]
    except TypeError:
        logging.error('Not an email file: {}'.format(file))
        return None
    if not encoding: return subject
    else: return subject.decode(encoding)

def export_csv(dir_list):
    with open('output.csv', 'w+', encoding='utf-8') as csv_file:
        csvwriter = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow(['Current path', 'Subject', 'File name', 'Move target'])
        for dir in dir_list:
            for subject in dir.subjects:
                for file in subject.files:
                    csvwriter.writerow([dir.current_path, subject.subject, file, dir.move_path])

def export_questionable_csv(dir_list):
    with open('output_questionable.csv', 'w+', encoding='utf-8') as csv_file:
        csvwriter = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow(['Current path', 'Subject', 'File name', 'Move target'])
        for dir in dir_list:
            for subject in dir.subjects:
                for file in subject.questionable_files:
                    csvwriter.writerow([dir.current_path, subject.subject, file, dir.move_path])

def export_info_csv(dir_list):
    with open('info.csv', 'w', encoding='utf-8') as csv_file:
        csvwriter = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow(['Directory', 'Subject'])
        for dir in dir_list:
            for subject in dir.subjects:
                csvwriter.writerow([dir.current_path, subject.subject])

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def move_files(dir):
    ensure_dir(dir.move_path)
    for subject in dir.subjects:
        for file in subject.files:
            current_full_path = dir.current_path + '/' + file
            move_full_path = dir.move_path + '/' + file
            if os.path.exists(current_full_path):
                logging.info('Moving file: {} | {}'.format(current_full_path, move_full_path))
                shutil.move(current_full_path, move_full_path)
            else:
                logging.error('Missing file: {}'.format(current_full_path))
                print('  !!!Missing file: ' + current_full_path)
    pass

def count():
    global FILE_TOTAL_COUNTER
    FILE_TOTAL_COUNTER += 1

def read_count():
    global FILE_READ_COUNTER
    FILE_READ_COUNTER +=1

def main():

    print('Interpreting input csv')
    dir_list = build_dir_list()
    export_info_csv(dir_list)
    dir_num = len(dir_list)
    print ('Compiling list')
    for dir in dir_list:
        print (str(dir_num) + ' - ' + dir.print_current_path())
        match_files(dir)
        dir_num -= 1

    export_csv(dir_list)
    export_questionable_csv(dir_list)

    logging.info("Total files in searched directories: {}".format(FILE_TOTAL_COUNTER))
    logging.info("Total files interpreted: {}".format(FILE_READ_COUNTER))

    dir_num = len(dir_list)
    print ('Moving files')
    for dir in dir_list:
        print (str(dir_num) + ' - ' + dir.print_current_path())
        #move_files(dir)
        dir_num -= 1

if __name__ == "__main__":
    main()
