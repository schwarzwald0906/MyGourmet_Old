import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:oktoast/oktoast.dart';
import 'package:photo_manager/photo_manager.dart';
import 'package:provider/provider.dart';
import 'package:image/image.dart' as img;

import 'classifier.dart';
import 'classifier_quant.dart';
import 'model/photo_provider.dart';
// import 'page/index_page.dart';
import 'widget/image_item_widget.dart';

final PhotoProvider provider = PhotoProvider();
final Set<String> validLabels = {
  'guacamole',
  'consomme',
  'hot pot',
  'trifle',
  'ice cream',
  'ice lolly',
  'French loaf',
  'bagel',
  'pretzel',
  'cheeseburger',
  'hotdog',
  'mashed potato',
  'head cabbage',
  'broccoli',
  'cauliflower',
  'zucchini',
  'spaghetti squash',
  'acorn squash',
  'butternut squash',
  'cucumber',
  'artichoke',
  'bell pepper',
  'cardoon',
  'mushroom',
  'Granny Smith',
  'strawberry',
  'orange',
  'lemon',
  'fig',
  'pineapple',
  'banana',
  'jackfruit',
  'custard apple',
  'pomegranate',
  'red wine',
  'espresso',
  'cup',
  'eggnog',
  'carbonara',
  'chocolate sauce',
  'dough',
  'meat loaf',
  'pizza',
  'potpie',
  'burrito',
};
void main() {
  runZonedGuarded(
    () => runApp(const _SimpleExampleApp()),
    (Object e, StackTrace s) {
      if (kDebugMode) {
        FlutterError.reportError(FlutterErrorDetails(exception: e, stack: s));
      }
      showToast('$e\n$s', textAlign: TextAlign.start);
    },
  );
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      systemNavigationBarColor: Colors.transparent,
    ),
  );
}

class _SimpleExampleApp extends StatelessWidget {
  const _SimpleExampleApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<PhotoProvider>.value(
      value: provider, // This is for the advanced usages.
      child: MaterialApp(
        title: 'Photo Manager Example',
        builder: (context, child) {
          if (child == null) return const SizedBox.shrink();
          return Banner(
            message: 'Debug',
            location: BannerLocation.bottomStart,
            child: OKToast(child: child),
          );
        },
        home: const _SimpleExamplePage(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}

class _SimpleExamplePage extends StatefulWidget {
  const _SimpleExamplePage({Key? key}) : super(key: key);

  @override
  _SimpleExamplePageState createState() => _SimpleExamplePageState();
}

class _SimpleExamplePageState extends State<_SimpleExamplePage> {
  /// Customize your own filter options.
  final FilterOptionGroup _filterOptionGroup = FilterOptionGroup(
    imageOption: const FilterOption(
      sizeConstraint: SizeConstraint(ignoreSize: true),
    ),
  );
  final int _sizePerPage = 50;

  AssetPathEntity? _path;
  List<AssetEntity>? _entities;
  int _totalEntitiesCount = 0;

  int _page = 0;
  bool _isLoading = false;
  bool _isLoadingMore = false;
  bool _hasMoreToLoad = true;
  late Classifier _classifier;
  // File? _image;
  // Image? _imageWidget;
  img.Image? fox;
  List<List<AssetEntity>> batchify(List<AssetEntity> list, int batchSize) {
    int len = list.length;
    List<List<AssetEntity>> batches = [];

    for (int i = 0; i < len; i += batchSize) {
      int end = (i+batchSize < len) ? i+batchSize : len;
      batches.add(list.sublist(i, end));
    }

    return batches;
  }

  Future<List<AssetEntity>> processEntities(List<AssetEntity> entities) async {
    List<AssetEntity> validEntities = [];
    List<List<AssetEntity>> batches = batchify(entities, 100);

    for (List<AssetEntity> batch in batches) {
      // List to hold all the futures
      List<Future<void>> futures = [];

      for (AssetEntity entity in batch) {
        // Add each process to the futures list
        futures.add(() async {
          var originBytes = await entity.originBytes;
          if (originBytes != null) {
            img.Image? imageInput = img.decodeImage(originBytes);
            if (imageInput != null) {
              var pred = _classifier.predict(imageInput);
              if (validLabels.contains(pred.label)) {
                validEntities.add(entity);
              }
            }
          }
        }());
      }

      // Wait for all the processes to finish
      await Future.wait(futures);
    }
    return validEntities;
  }

  Future<void> _requestAssets() async {
    setState(() {
      _isLoading = true;
    });
    // Request permissions.
    final PermissionState ps = await PhotoManager.requestPermissionExtend();
    if (!mounted) {
      return;
    }
    // Further requests can be only proceed with authorized or limited.
    if (!ps.hasAccess) {
      setState(() {
        _isLoading = false;
      });
      showToast('Permission is not accessible.');
      return;
    }
    // Obtain assets using the path entity.
    final List<AssetPathEntity> paths = await PhotoManager.getAssetPathList(
      onlyAll: true,
      filterOption: _filterOptionGroup,
    );
    if (!mounted) {
      return;
    }
    // Return if not paths found.
    if (paths.isEmpty) {
      setState(() {
        _isLoading = false;
      });
      showToast('No paths found.');
      return;
    }
    setState(() {
      _path = paths.first;
    });
    _totalEntitiesCount = await _path!.assetCountAsync;

    final List<AssetEntity> entities = await _path!.getAssetListPaged(
      page: 0,
      size: _sizePerPage,
    );

    if (!mounted) {
      return;
    }

    List<AssetEntity> validEntities = await processEntities(entities);

    setState(() {
      _entities = validEntities;
      _isLoading = false;
      _hasMoreToLoad = _entities!.length < _totalEntitiesCount;
    });
  }

  Future<void> _loadMoreAsset() async {
    final List<AssetEntity> entities = await _path!.getAssetListPaged(
      page: _page + 1,
      size: _sizePerPage,
    );
    if (!mounted) {
      return;
    }
    setState(() {
      _entities!.addAll(entities);
      _page++;
      _hasMoreToLoad = _entities!.length < _totalEntitiesCount;
      _isLoadingMore = false;
    });
  }

  Widget _buildBody(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator.adaptive());
    }
    if (_path == null) {
      return const Center(child: Text('Request paths first.'));
    }
    if (_entities?.isNotEmpty != true) {
      return const Center(child: Text('No assets found on this device.'));
    }
    return GridView.custom(
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
      ),
      childrenDelegate: SliverChildBuilderDelegate(
        (BuildContext context, int index) {
          if (index == _entities!.length - 8 &&
              !_isLoadingMore &&
              _hasMoreToLoad) {
            _loadMoreAsset();
          }
          final AssetEntity entity = _entities![index];
          return ImageItemWidget(
            key: ValueKey<int>(index),
            entity: entity,
            option: const ThumbnailOption(size: ThumbnailSize.square(200)),
          );
        },
        childCount: _entities!.length,
        findChildIndexCallback: (Key key) {
          // Re-use elements.
          if (key is ValueKey<int>) {
            return key.value;
          }
          return null;
        },
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _classifier = ClassifierQuant();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('photo_manager')),
      body: Column(
        children: <Widget>[
          const Padding(
            padding: EdgeInsets.all(8.0),
            child: Text(
              'This page will only obtain the first page of assets '
              'under the primary album (a.k.a. Recent). '
              'If you want more filtering assets, '
              'head over to "Advanced usages".',
            ),
          ),
          Expanded(child: _buildBody(context)),
        ],
      ),
      // persistentFooterButtons: <TextButton>[
      //   TextButton(
      //     onPressed: () {
      //       Navigator.of(context).push<void>(
      //         MaterialPageRoute<void>(builder: (_) => const IndexPage()),
      //       );
      //     },
      //     child: const Text('Advanced usages'),
      //   ),
      // ],
      floatingActionButton: FloatingActionButton(
        onPressed: _requestAssets,
        child: const Icon(Icons.developer_board),
      ),
    );
  }
}
