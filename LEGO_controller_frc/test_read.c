#include <windows.h>
#include <stdio.h>

//gcc test_read.c -o test_read.exe

typedef struct {
    volatile LONG state;          // 0=lu 1=commande
    char buffer[1024];
    volatile LONG mode_code;
    volatile LONG response_count;
    char response[500][1024];
} SharedHub;

int main()
{
    HANDLE h =
        OpenFileMappingA(
            FILE_MAP_READ,
            FALSE,
            "FRC_TO_CONTROLLER_HUB"
        );

    if (!h)
    {
        printf(
            "open fail %lu\n",
            GetLastError()
        );

        return 1;
    }

    SharedHub* s =
        MapViewOfFile(
            h,
            FILE_MAP_READ,
            0,
            0,
            sizeof(SharedHub)
        );

    if (!s)
    {
        printf(
            "map fail\n"
        );

        return 1;
    }

    printf(
        "state=%ld\n",
        s->state
    );

    printf(
        "buffer=%s\n",
        s->buffer
    );

    printf(
        "mode=%ld\n",
        s->mode_code
    );

    printf(
        "responses=%ld\n",
        s->response_count
    );

    for (
        int i = 0;
        i < s->response_count;
        i++
    )
    {
        printf(
            "[%d] %s\n",
            i,
            s->response[i]
        );
    }

    UnmapViewOfFile(s);
    CloseHandle(h);

    return 0;
}
