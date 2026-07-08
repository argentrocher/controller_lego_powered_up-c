#include <windows.h>
#include <stdio.h>
#include <stdbool.h>
#include <shlwapi.h>

// Structure pour partager les handles entre les threads
typedef struct {
    HANDLE hReadPipe;      // Pipe pour lire stdout de l'exe
    HANDLE hWritePipeIn;   // Pipe pour écrire vers stdin de l'exe
    HANDLE hProcess;       // Handle du processus
    bool running;          // Flag pour arrêter le thread
} ProcessPipe;

ProcessPipe pipe; //global

bool autentified_pipe = false; // le processus envoie "Controller LEGO Powered up (c)" ... pour savoir que le processus est correct

//gcc controller_test.c -o controller_test.exe -lshlwapi

#define SHARED_NAME "FRC_TO_CONTROLLER_HUB"
#define SHARED_MUTEX_NAME "FRC_TO_CONTROLLER_HUB_MUTEX"

HANDLE frc_mutex = NULL;

#define APP_PIPE_NAME "test_command_lego_powerup.exe"
#define APP_PIPE_ARG "--cache"

bool send_command(const char *command); //envoie de commande au pipe APP_PIPE_NAME sur stdin

typedef struct {
    volatile LONG state;          // 0=lu 1=commande
    char buffer[1024];
    volatile LONG mode_code;
    volatile LONG response_count;
    char response[500][1024];
} SharedHub;

SharedHub* frc_shared = NULL;
HANDLE frc_map = NULL;

char frc_exe[MAX_PATH];
char frc_script[MAX_PATH];

//charger l'exeécutable .frc (fr-simplecodeX.X.X.exe)
bool load_frc_exe() {
    DWORD sz = MAX_PATH;
    return AssocQueryStringA(
        0,
        ASSOCSTR_EXECUTABLE,
        ".frc",
        NULL,
        frc_exe,
        &sz
    ) == S_OK;
}

bool init_frc_bridge()
{
    frc_map =
        CreateFileMappingA(
            INVALID_HANDLE_VALUE,
            NULL,
            PAGE_READWRITE,
            0,
            sizeof(SharedHub),
            SHARED_NAME
        );

    if (!frc_map)
        return false;

    frc_shared =
        (SharedHub*)
        MapViewOfFile(
            frc_map,
            FILE_MAP_ALL_ACCESS,
            0,
            0,
            sizeof(SharedHub)
        );

    if (!frc_shared)
        return false;

    //mutex
    frc_mutex = CreateMutexA(
        NULL,
        FALSE,
        SHARED_MUTEX_NAME
    );

    if (!frc_mutex)
        return false;

    frc_shared->state = 0;
    frc_shared->mode_code = 0;

    return true;
}

//envoie la reponse sur le tampon global pour fr-simplecode dans les reponses (code_mode & 1 == 1 pour les stdout du controller)
void push_response_frc(const char* line, bool type_file) {
    if (!frc_shared)
        return;

    //mutex
    WaitForSingleObject(frc_mutex, INFINITE);

    LONG count = frc_shared->response_count;

    if (!type_file) {
        // ---------- PILE (LIFO) ----------

        // plein -> retire 2 anciens
        if (count >= 500) {
            for (int i = 2; i < count; i++){
                strcpy(frc_shared->response[i - 2],frc_shared->response[i]);
            }
            count -= 2;
            frc_shared->response_count = count;
        }
        strncpy(frc_shared->response[count],line,1023);
        frc_shared->response[count][1023] = '\0';

    } else {
        // ---------- FILE (FIFO) ----------

        if (count >= 500) {
            // On supprime les 2 derniers
            count -= 2;
            frc_shared->response_count = count;
        }

        // Décalage vers la droite
        for (int i = count; i > 0; i--) {
            strcpy(frc_shared->response[i],frc_shared->response[i - 1]);
        }

        strncpy(frc_shared->response[0], line, 1023);
        frc_shared->response[0][1023] = '\0';

    }

    /*InterlockedIncrement(
        &frc_shared->response_count
    );*/
    frc_shared->response_count++;

    FlushViewOfFile(frc_shared,sizeof(SharedHub));

    ReleaseMutex(frc_mutex); //libérer mutex
}

DWORD WINAPI poll_frc_output(LPVOID p) {
    while (pipe.running) {
        Sleep(3);

        if (!frc_shared)
            continue;

        //mutex
        WaitForSingleObject(frc_mutex, INFINITE);

        /*if (InterlockedCompareExchange(
                &frc_shared->state, 0, 1) == 1) */
        if (frc_shared->state){

            //printf("> %s\n", frc_shared->buffer);
            size_t len_buf = strlen(frc_shared->buffer);
            if (len_buf > 0) {
                char local[1024];
                strncpy(local, frc_shared->buffer, sizeof(local) - 1);
                local[sizeof(local) - 1] = '\0';

                char *line = local;

                while (*line) {
                    char *next = strchr(line, '\n');

                    if (next) {
                        *next = '\0';
                        next++;
                    }

                    // Supprime les \r \t ' ' en fin de ligne
                    size_t len = strlen(line);
                    while (len > 0 && (line[len - 1] == '\r' || line[len - 1] == '\t' || line[len - 1] == ' ')) {
                        line[--len] = '\0';
                    }

                    if (line[0] != '\0') {
                        char cmd[1025];
                        snprintf(cmd, sizeof(cmd), "%s\n", line);
                        send_command(cmd);
                    }

                    if (!next) break;

                    line = next;
                }
            }
            frc_shared->state = 0;
            FlushViewOfFile(frc_shared, sizeof(SharedHub));
        }

        ReleaseMutex(frc_mutex); //libérer mutex
    }
    return 0;
}

DWORD WINAPI run_frc_thread(LPVOID param) {
    char* arg = (char*)param;
    char cmd[4096];

    snprintf(
        cmd,
        sizeof(cmd),
        "\"%s\" --start:\"%s\" --arg:\"%s\"",
        frc_exe,
        frc_script,
        arg
    );

    STARTUPINFOA si = {
        sizeof(si)
    };

    PROCESS_INFORMATION pi;

    if (
        CreateProcessA(
            NULL,
            cmd,
            NULL,
            NULL,
            FALSE,
            0,
            NULL,
            NULL,
            &si,
            &pi
        )
    )
    {
        CloseHandle(
            pi.hThread
        );

        CloseHandle(
            pi.hProcess
        );
    }

    free(arg);

    return 0;
}

void launch_frc(const char* arg) {
    char* copy = _strdup(arg);

    CreateThread(
        NULL,
        0,
        run_frc_thread,
        copy,
        0,
        NULL
    );
}

// Fonction appelée à chaque fois qu'une ligne est lue depuis stdout
bool on_event(const char *line) {
    if (!autentified_pipe) {
        if (strncmp(line,"Controller LEGO Powered up (c)",30)==0 || strncmp(line,"✅ CHAR_UUID remplacé par valeur du fichier char_uuid_lego_controller.txt:",76)==0) {
            autentified_pipe = true;
            launch_frc("default");
            CreateThread(
                NULL,
                0,
                poll_frc_output,
                NULL,
                0,
                NULL
            );
            return true;
        } else {
            if (strncmp(line,"⚠",1)==0) printf("%s", line);
            else printf("le processus appeler '%s' est invalide, verifer la compatibilité !", APP_PIPE_NAME);
            return false;
        }
    }
    //affiche les commandes reçu par PIPE si mode_code n'a pas la 5 ème bit à 1 (valeur 16)
    if (!(frc_shared->mode_code & 16)) printf("%s", line);

    if (frc_shared->mode_code & 1) {
        //pile ou file en fonction du bit 2 de mode_code
        if (frc_shared->mode_code & 2)
            push_response_frc(line, true);
        else
            push_response_frc(line, false);
    } else
        launch_frc(line);

    return true;
}

// Thread dédié à la lecture de stdout
DWORD WINAPI read_stdout_thread(LPVOID lpParam) {
    char buffer[4096];
    DWORD bytesRead;

    while (pipe.running) {
        if (ReadFile(pipe.hReadPipe, buffer, sizeof(buffer) - 1, &bytesRead, NULL) && bytesRead > 0) {
            buffer[bytesRead] = '\0';
            bool resu = on_event(buffer);  // Appelle on_event pour chaque ligne
            if (!resu) pipe.running = false;
        } else {
            // Erreur ou fin de flux
            pipe.running = false;
        }
    }
    return 0;
}

// Fonction pour envoyer une commande à l'exe
bool send_command(const char *command) {
    DWORD bytesWritten;
    bool success = WriteFile(pipe.hWritePipeIn, command, strlen(command), &bytesWritten, NULL);
    if (!success) {
        fprintf(stderr, "Erreur WriteFile\n");
    }
    return success;
}

// Initialise le processus et les pipes
bool start_process(const char *executable, const char *arg) {
    SECURITY_ATTRIBUTES sa = { sizeof(SECURITY_ATTRIBUTES), NULL, TRUE };
    HANDLE hWritePipe, hReadPipeIn;
    STARTUPINFO si = { sizeof(STARTUPINFO) };
    PROCESS_INFORMATION pi;

    // Créer le pipe pour stdout
    if (!CreatePipe(&pipe.hReadPipe, &hWritePipe, &sa, 0)) {
        fprintf(stderr, "Erreur CreatePipe (stdout)\n");
        return false;
    }

    // Créer le pipe pour stdin
    if (!CreatePipe(&hReadPipeIn, &pipe.hWritePipeIn, &sa, 0)) {
        fprintf(stderr, "Erreur CreatePipe (stdin)\n");
        CloseHandle(pipe.hReadPipe);
        CloseHandle(hWritePipe);
        return false;
    }

    // Configurer STARTUPINFO
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = hWritePipe;  // Redirige stdout vers notre pipe
    si.hStdInput = hReadPipeIn;   // Redirige stdin depuis notre pipe
    si.hStdError = hWritePipe;   // Redirige stderr aussi

    char cmdLine[4096];

    if (arg && arg[0] != '\0') {
        snprintf(
            cmdLine,
            sizeof(cmdLine),
            "\"%s\" %s",
            executable,
            arg
        );
    } else {
        snprintf(
            cmdLine,
            sizeof(cmdLine),
            "\"%s\"",
            executable
        );
    }

    // Lancer le processus
    if (!CreateProcess(
        NULL, //(char *)executable, // Exécutable nom à lancer (pas utiliser si on met un chemin)
        cmdLine,  //La commande
        NULL,
        NULL,
        TRUE,  // Hériter les handles
        0,
        NULL,
        NULL,
        &si,
        &pi
    )) {
        fprintf(stderr, "Erreur CreateProcess\n");
        CloseHandle(pipe.hReadPipe);
        CloseHandle(hWritePipe);
        CloseHandle(hReadPipeIn);
        CloseHandle(pipe.hWritePipeIn);
        return false;
    }

    // Fermer les handles inutiles dans le parent
    CloseHandle(hWritePipe);
    CloseHandle(hReadPipeIn);

    // Stocker le handle du processus
    pipe.hProcess = pi.hProcess;
    pipe.running = true;

    // Lancer le thread de lecture
    HANDLE hThread = CreateThread(NULL, 0, read_stdout_thread, NULL, 0, NULL);
    if (hThread == NULL) {
        fprintf(stderr, "Erreur CreateThread\n");
        CloseHandle(pipe.hReadPipe);
        CloseHandle(pipe.hWritePipeIn);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return false;
    }
    CloseHandle(hThread);  // On ne ferme pas le thread ici, il s'arrêtera avec pipe->running

    return true;
}

// Nettoie les ressources
void cleanup_process() {
    pipe.running = false;  // Arrête le thread
    CloseHandle(pipe.hReadPipe);
    CloseHandle(pipe.hWritePipeIn);
    CloseHandle(pipe.hProcess);
}

// Exemple d'utilisation
int main(int argc, char *argv[]) {

    SetConsoleOutputCP(65001);
    SetConsoleCP(65001);

    load_frc_exe();

    if (argc>=2) strncpy(frc_script, argv[1], sizeof(frc_script));
    else strcpy(frc_script,"main_lego.frc");

    bool create_var = init_frc_bridge();
    if (!create_var) {
        printf("Impossible de créer les variables globales de mémoire !\n");
        return 1;
    }

    if (!start_process(APP_PIPE_NAME, APP_PIPE_ARG)) {
        return 1;
    }

    printf("Entrez une commande (ou 'exit' pour quitter) :\n");

    // Exemple : envoyer des commandes en boucle
    while (pipe.running) {
        char input[1024];
        fgets(input, sizeof(input), stdin);

        if (strncmp(input, "exit", 4) == 0) {
            break;
        }

        if (frc_shared && (frc_shared->mode_code & 4)) {
            char input2[1024];
            if (frc_shared->mode_code & 8) strcpy(input2, input);
            else snprintf(input2, sizeof(input2), "PROMPT=%s", input);
            if (frc_shared->mode_code & 1) {
                //pile ou file en fonction du bit 2 de mode_code
                if (frc_shared->mode_code & 2)
                    push_response_frc(input2, true);
                else
                    push_response_frc(input2, false);
            } else
                launch_frc(input2);
        } else {
            send_command(input);  // Envoie la commande à l'exe
        }
    }

    cleanup_process();
    return 0;
}
