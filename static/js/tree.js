$(function () {
    $('#recording-tree').jstree({
        core: {
            data: {
                url: '/api/recordings/tree',
                dataType: 'json',
            },
            themes: {
                name: 'default',
                dots: true,
                icons: true,
            },
        },
        plugins: ['types', 'sort'],
        types: {
            folder: {
                icon: 'jstree-folder',
            },
            video: {
                icon: 'jstree-file',
            },
        },
        sort: function (a, b) {
            const aNode = this.get_node(a);
            const bNode = this.get_node(b);
            const aIsFolder = aNode.type === 'folder';
            const bIsFolder = bNode.type === 'folder';
            if (aIsFolder && !bIsFolder) return -1;
            if (!aIsFolder && bIsFolder) return 1;
            return aNode.text.localeCompare(bNode.text);
        },
    });

    $('#recording-tree').on('select_node.jstree', function (e, data) {
        const node = data.node;
        if (node.type === 'video' && node.data && node.data.path) {
            const videoPath = encodeURIComponent(node.data.path);
            const container = $('#video-container');
            container.html(`
                <video class="video-player w-100" controls preload="metadata">
                    <source src="/api/recordings/stream?path=${videoPath}" type="video/mp4">
                    Tu navegador no soporta video HTML5.
                </video>
                <div class="mt-2">
                    <a href="/api/recordings/stream?path=${videoPath}" class="btn btn-sm btn-outline-primary" download>
                        Descargar
                    </a>
                </div>
            `);
        } else if (node.type === 'folder') {
            $('#video-container').html(`
                <p class="text-muted my-5">Selecciona un archivo de video para previsualizarlo</p>
            `);
        }
    });

    $('#recording-tree').on('loaded.jstree', function () {
        $('#recording-tree').jstree('open_all');
    });
});
