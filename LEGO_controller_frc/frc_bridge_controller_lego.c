#include <windows.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>

#define SHARED_NAME "FRC_TO_CONTROLLER_HUB"
#define SHARED_MUTEX_NAME "FRC_TO_CONTROLLER_HUB_MUTEX"


#define BUFFER_SIZE 1024

// gcc -shared frc_bridge_controller_lego.c -o frc_bridge_controller_lego.dll

typedef struct {
    volatile LONG state;          // 0=lu 1=commande
    char buffer[1024];
    volatile LONG mode_code;
    volatile LONG response_count;
    char response[500][1024];
} SharedHub;

static HANDLE hMap = NULL;
static SharedHub* hub = NULL;
HANDLE hmutex = NULL; //mutex global

int view_err_dll = 1; //affiche les printf si valeur, sinon n'affiche pas avec 0

void close_connect() {
    if (hub) UnmapViewOfFile(hub);
    hub = NULL;
    if (hMap) CloseHandle(hMap);
    hMap = NULL;
    if (hmutex) CloseHandle(hmutex);
    hmutex = NULL;
}

static int connect_shared()
{
    if (hub)
        return 1;

    BOOL created = FALSE;

    // Essaye d'ouvrir
    hMap =
        OpenFileMappingA(
            FILE_MAP_ALL_ACCESS,
            FALSE,
            SHARED_NAME
        );

    // Si absent -> créer avant, maintenant, juste exception pour exit
    if (!hMap)
    {
        if (view_err_dll) printf("ERROR: GLOBALS VARS ARE DESTROY -> frc_bridge_controller_lego.dll IS STOPED !\n");
        /*hMap =
            CreateFileMappingA(
                INVALID_HANDLE_VALUE,
                NULL,
                PAGE_READWRITE,
                0,
                sizeof(SharedHub),
                SHARED_NAME
            );

        if (!hMap)
            return 0;

        created = (GetLastError() != ERROR_ALREADY_EXISTS);*/
        return 0;
    }

    hub =
        (SharedHub*)
        MapViewOfFile(
            hMap,
            FILE_MAP_ALL_ACCESS,
            0,
            0,
            sizeof(SharedHub)
        );

    if (!hub)
    {
        CloseHandle(hMap);
        hMap = NULL;
        return 0;
    }

    if (created)
    {
        hub->state = 0;
        hub->buffer[0] = '\0';
        hub->mode_code = 0;
    }

    if (!hmutex) {
        hmutex = OpenMutexA(MUTEX_ALL_ACCESS, FALSE, SHARED_MUTEX_NAME);
    }
    if (!hmutex) {
        if (view_err_dll) printf("ERROR: GLOBALS MUTEX ARE DESTROY -> frc_bridge_controller_lego.dll IS STOPED !\n");
        close_connect();
        return 0;
    }

    return 1;
}

__declspec(dllexport)
void set_err_dll(int val) {
    view_err_dll = val;
}

__declspec(dllexport)
int isvalid_mac_addr(char *addr) {
    if (addr == NULL)
        return 0;

    // Longueur exacte : 17 caractères
    if (strlen(addr) != 17)
        return 0;

    char sep = addr[2];

    // Séparateur autorisé uniquement ':'
    if (sep != ':')
        return 0;

    for (int i = 0; i < 17; i++) {
        if ((i + 1) % 3 == 0) {
            // Position des séparateurs
            if (addr[i] != sep)
                return 0;
        } else {
            // Caractère hexadécimal
            if (!isxdigit((unsigned char)addr[i])) {
                return 0;
            }
        }
    }
    return 1;
}

__declspec(dllexport)
int write_data(const char* command) {
    if (!command)
        return 0;

    if (!connect_shared())
        return 0;

    //mutex
    WaitForSingleObject(hmutex, INFINITE);

    // Écrit uniquement si libre
    /*if (
        InterlockedCompareExchange(
            &hub->state,
            1,
            0
        ) != 0
    )*/
    if (hub->state){
        ReleaseMutex(hmutex); //libérer mutex
        close_connect();
        return 0;
    }
    hub->state = 1;
    strncpy(
        hub->buffer,
        command,
        BUFFER_SIZE - 1
    );

    hub->buffer[
        BUFFER_SIZE - 1
    ] = '\0';

    FlushViewOfFile(hub,sizeof(SharedHub));

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
    return 1;
}

__declspec(dllexport)
int is_read_data() {
    if (!connect_shared())
        return 0;
    int resu = (hub->state == 0);
    close_connect();
    return resu;
}

__declspec(dllexport)
void mark_read_data() {
    if (!connect_shared())
        return;

    //mutex
    WaitForSingleObject(hmutex, INFINITE);

    /*InterlockedExchange(
        &hub->state,
        0
    );*/
    hub->state = 0;

    FlushViewOfFile(hub,sizeof(SharedHub));

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
}

__declspec(dllexport)
void set_mode(int mode) {
    if (!connect_shared())
        return;

     //mutex
    WaitForSingleObject(hmutex, INFINITE);

    hub->mode_code = mode;

    FlushViewOfFile(hub, sizeof(SharedHub));

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
}

__declspec(dllexport)
int get_mode() {
    if (!connect_shared())
        return 0;

     //mutex
    WaitForSingleObject(hmutex, INFINITE);

    int r = hub->mode_code;

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
    return r;
}

__declspec(dllexport)
int get_response_count() {
    if (!connect_shared())
        return 0;

    //mutex
    WaitForSingleObject(hmutex, INFINITE);

    int r = hub->response_count;

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
    return r;
}

__declspec(dllexport)
int push_response(const char* txt) {
    if (!txt)
        return 0;

    if (!connect_shared())
        return 0;

    LONG idx = hub->response_count;

    if (idx >= 500) {
        close_connect();
        return 0;
    }

    //mutex
    WaitForSingleObject(hmutex, INFINITE);

    strncpy(hub->response[idx], txt, 1023);

    hub->response[idx][1023] = '\0';

    /*InterlockedIncrement(
        &hub->response_count
    );*/
    hub->response_count++;

    FlushViewOfFile(hub,sizeof(SharedHub));

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
    return 1;
}

__declspec(dllexport)
char* pop_response() {
    static char out[1024]="NULL";
    if (!connect_shared())
        return out;

    //mutex
    WaitForSingleObject(hmutex, INFINITE);

    LONG idx = hub->response_count-1;
    if (hub->response_count>0) {
        strncpy(out, hub->response[idx],1023);
        out[1023] = '\0';

        /*InterlockedDecrement(
            &hub->response_count
        );*/
        hub->response_count--;

        FlushViewOfFile(hub, sizeof(SharedHub));
    }

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
    return out;
}

__declspec(dllexport)
void clear_all_response() {
    if (!connect_shared())
        return;

    //mutex
    WaitForSingleObject(hmutex, INFINITE);

    hub->response_count = 0;

    FlushViewOfFile(hub, sizeof(SharedHub));

    ReleaseMutex(hmutex); //libérer mutex

    close_connect();
}

__declspec(dllexport)
int wait_event(int timeout_ms) {
    if (!connect_shared())
        return 0;

    if (!(hub->mode_code & 1)) {
        close_connect();
        return 0;
    }

    LONG start_count = hub->response_count;

    close_connect();

    DWORD start_tick = GetTickCount();

    for (;;) {
        Sleep(3);

        if (!connect_shared())
            return 0;

        //mutex
        WaitForSingleObject(hmutex, INFINITE);

        LONG current = hub->response_count;

        ReleaseMutex(hmutex); //libérer mutex

        close_connect();

        if (current != start_count)
            return 1;

        if (timeout_ms > 0 && (GetTickCount() - start_tick) >= (DWORD)timeout_ms)
            return 2;
    }
}

__declspec(dllexport)
int wait_event_startswith(const char* prefix) {
    if (!prefix)
        return 0;

    if (!connect_shared())
        return 0;

    if (!(hub->mode_code & 1)) {
        close_connect();
        return 0;
    }

    LONG last_count = hub->response_count;

    close_connect();

    size_t prefix_len = strlen(prefix);

    for (;;) {
        Sleep(3);

        if (!connect_shared())
            return 0;

        //mutex
        WaitForSingleObject(hmutex, INFINITE);

        LONG current = hub->response_count;

        if (current != last_count && current > 0) {
            char* last = hub->response[current - 1];

            if (strncmp(last, prefix, prefix_len) == 0) {
                ReleaseMutex(hmutex); //libérer mutex
                close_connect();
                return 1;
            }
            last_count =  current;
        }
        ReleaseMutex(hmutex); //libérer mutex
        close_connect();
    }
}

BOOL APIENTRY DllMain(
    HMODULE h,
    DWORD reason,
    LPVOID r
)
{
    /*
    if (
        reason
        ==
        DLL_PROCESS_DETACH
    )
    {
        if (hub)
        {
            UnmapViewOfFile(
                hub
            );

            hub = NULL;
        }

        if (hMap)
        {
            CloseHandle(
                hMap
            );

            hMap = NULL;
        }
    }*/

    return TRUE;
}
