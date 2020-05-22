import plotly.graph_objs as go
import ipywidgets as widgets

import netCDF4
import numpy
import os
import sys
import warnings

#warnings.simplefilter('ignore')


class StatsViewer(object):
    def __init__(self, inputFile):
        dataset = netCDF4.Dataset(inputFile, 'r')

        self.models      = [ 'all' ] + [ x for x in dataset.variables['model_names'][...] ]
        self.scenarios   = [ 'all' ] + [ x for x in dataset.variables['scenario_names'][...] ]
        self.yearRanges  = [ 'all' ] + [ x for x in dataset.variables['year_ranges'][...] ]

        self.seasons = [ x for x in dataset.variables['season_names'][...] ]
        self.months  = [ x for x in dataset.variables['month_names'][...] ]

        self.clims  = [ 'all seasons', 'all months' ] + self.seasons + self.months

        self.latRanges = [ 'all' ]

        for low, high in dataset.variables['lat_bounds'][:]:
            low  = '%dS' % ( -low, )  if 0 > low  else '%dN' % ( low, )
            high = '%dN' % ( -high, ) if 0 > high else '%dN' % ( high, )

            self.latRanges.append('%s-%s' % (low, high))

        self.lonRanges = [ 'all' ]

        for low, high in dataset.variables['lon_bounds'][:]:
            low  = '%dW' % ( -low, )  if 0 > low  else '%dE' % ( low, )
            high = '%dW' % ( -high, ) if 0 > high else '%dE' % ( high, )

            self.lonRanges.append('%s-%s' % (low, high))

        self.yearBounds  = dataset.variables['year_bounds'][...]
        self.monthlyClim  = dataset.variables['monthly_clim'][...]
        self.seasonalClim = dataset.variables['seasonal_clim'][...]

        self.monthlyValues = dataset.variables['monthly_clim'][...]
        self.monthlyStdevs = dataset.variables['monthly_clim_stdev'][...]

        self.seasonalValues = dataset.variables['seasonal_clim'][...]
        self.seasonalStdevs = dataset.variables['seasonal_clim_stdev'][...]

        self.valueUnits = dataset.variables['seasonal_clim'].units

        self.spatialMeanOptions = (
            'none',
            'latitude',
            'longitude',
            'lat/lon'
        )

        self.xAxisOptions = (
            'models',
            'scenarios',
            'years',
            'climatology time',
            'latitude',
            'longitude'
        )

        self.yAxisOptions = (
            'values',
            'ratio to historical'
        )

        self.yUnitsOptions = (
            '1/week',
            '1/avg month',
            '1/avg season',
            '1/avg year'
        )

        self.yUnitsFactors = {
            '1/week':       1.0,
            '1/avg month':  365.25 / 7.0 / 12.0, # Convert weekly rate to average yearly then divide by 12.
            '1/avg season': 365.25 / 7.0 / 4.0,  # Convert weekly rate to average yearly then divide by 4.
            '1/avg year':   365.25 / 7.0         # Convert weekly rate to average yearly.
        }

        self.figure = go.FigureWidget()


    def interact(self):
        modelSelection       = widgets.SelectMultiple(description = 'Model:', options = self.models, value = ('all',))
        scenarioSelection    = widgets.SelectMultiple(description = 'Scenario:', options = self.scenarios, value = ('all',))
        climSelection        = widgets.SelectMultiple(description = 'Climatology:', options = self.clims, value = ('all seasons',))
        rangeSelection       = widgets.SelectMultiple(description = 'Years:', options = self.yearRanges, value = ('all',))
        latSelection         = widgets.SelectMultiple(description = 'Latitude:', options = self.latRanges, value = ('all',))
        lonSelection         = widgets.SelectMultiple(description = 'Longitude:', options = self.lonRanges, value = ('all',))
        spatialMeanSelection = widgets.Select(description = 'Spatial Mean:', options = self.spatialMeanOptions, value = 'none')
        xAxisSelection       = widgets.Select(description = 'X Axis:', options = self.xAxisOptions, value = 'climatology time')
        yAxisSelection       = widgets.Select(description = 'Y Axis:', options = self.yAxisOptions, value = 'values')
        yUnitsSelection      = widgets.Select(description = 'Y Units:', options = self.yUnitsOptions, value = '1/week')

        argDict = {
            'modelsSelected':      modelSelection,
            'scenariosSelected':   scenarioSelection,
            'climsSelected':       climSelection,
            'rangesSelected':      rangeSelection,
            'latsSelected':        latSelection,
            'lonsSelected':        lonSelection,
            'spatialMeanSelected': spatialMeanSelection,
            'xAxisSelected':       xAxisSelection,
            'yAxisSelected':       yAxisSelection,
            'yUnitsSelected':      yUnitsSelection
        }

        interactive = widgets.interactive(self.displayChart, **argDict)

        row1 = widgets.HBox((modelSelection, scenarioSelection, climSelection))
        row2 = widgets.HBox((rangeSelection, latSelection, lonSelection))
        row3 = widgets.HBox((spatialMeanSelection, xAxisSelection, yAxisSelection, yUnitsSelection))

        app = widgets.VBox((row1, row2, row3, self.figure, interactive.children[-1]))

        return app


    def displayChart(self, modelsSelected, scenariosSelected, climsSelected,
                     rangesSelected, latsSelected, lonsSelected,
                     spatialMeanSelected, xAxisSelected, yAxisSelected, yUnitsSelected):
        # Build the data selection.
        #
        if 'all seasons' == climsSelected[0]:
            climsSelected = list(self.seasons)
            theClims      = self.seasons
            values        = self.seasonalValues
            stdevs        = self.seasonalStdevs
        elif 'all months' == climsSelected[0]:
            climsSelected = list(self.months)
            theClims      = self.months
            values        = self.monthlyValues
            stdevs        = self.monthlyStdevs
        elif set(climsSelected) <= set(self.seasons):
            theClims = self.seasons
            values   = self.seasonalValues
            stdevs   = self.seasonalStdevs
        elif set(climsSelected) <= set(self.months):
            theClims = self.months
            values   = self.monthlyValues
            stdevs   = self.monthlyStdevs
        else:
            raise ValueError('Selecting a mix of months and seasons is forbidden')

        values = values * self.yUnitsFactors[yUnitsSelected]

        if 'all' == modelsSelected[0]:
            modelsSelected = self.models[1:]

        if 'all' == scenariosSelected[0]:
            scenariosSelected = self.scenarios[1:]
        
        if 'all' == rangesSelected[0]:
            rangesSelected = self.yearRanges[1:]
        
        if 'all' == latsSelected[0]:
            latsSelected = self.latRanges[1:]
        
        if 'all' == lonsSelected[0]:
            lonsSelected = self.lonRanges[1:]
        
        if 'values' != yAxisSelected:
            scenariosSelected = list(scenariosSelected)

            try:
                scenariosSelected.remove('historical')
            except:
                pass

        indices  = ( [], [], [], [], [], [] )
        indexMap = ( [], [], [], [], [], [] )
        names    = ( [], [], [], [], [], [] )
        
        for model in modelsSelected:
            modelIndex = self.models.index(model) - 1

            for scenario in scenariosSelected:
                scenarioIndex = self.scenarios.index(scenario) - 1
                
                for yearRange in rangesSelected:
                    rangeIndex = self.yearRanges.index(yearRange) - 1
                    
                    if 0 == values[modelIndex, scenarioIndex, rangeIndex].count():
                        continue

                    if model not in names[0]:
                        indexMap[0].append(modelIndex)
                        names[0].append(model)
                    
                    if scenario not in names[1]:
                        indexMap[1].append(scenarioIndex)
                        names[1].append(scenario)
                    
                    if yearRange not in names[2]:
                        indexMap[2].append(rangeIndex)
                        names[2].append(yearRange)
                    
                    for clim in climsSelected:
                        climIndex = theClims.index(clim)
                    
                        if clim not in names[3]:
                            indexMap[3].append(climIndex)
                            names[3].append(clim)
                        
                        for latRange in latsSelected:
                            latIndex = self.latRanges.index(latRange) - 1
                        
                            if latRange not in names[4]:
                                indexMap[4].append(latIndex)
                                names[4].append(latRange)
                            
                            for lonRange in lonsSelected:
                                lonIndex = self.lonRanges.index(lonRange) - 1
                        
                                if lonRange not in names[5]:
                                    indexMap[5].append(lonIndex)
                                    names[5].append(lonRange)
                            
                                indices[0].append(modelIndex)
                                indices[1].append(scenarioIndex)
                                indices[2].append(rangeIndex)
                                indices[3].append(climIndex)
                                indices[4].append(latIndex)
                                indices[5].append(lonIndex)

        shape = (
            len(names[0]),
            len(names[1]),
            len(names[2]),
            len(names[3]),
            len(names[4]),
            len(names[5])
        )

        plotValues = numpy.ma.masked_all(shape, dtype = values.dtype)

        def mapIndices(mapList, indices):
            mappedIndices = list()

            for mapper, index in zip(mapList, indices):
                mappedIndices.append(mapper.index(index))

            return tuple(mappedIndices)

        for inIndices in zip(*indices):

            outIndices = mapIndices(indexMap, inIndices)

            plotValues[outIndices] = values[inIndices]

        historicalValues = None

        if 'values' != yAxisSelected:
            historicalIndices  = ( [], [], [], [], [], [] )
            historicalIndexMap = ( [], [], [], [], [], [] )
            historicalNames    = ( [], [], [], [], [], [] )

            scenarioIndex = self.scenarios.index('historical') - 1


            for model in modelsSelected:
                if model not in names[0]:
                    continue

                modelIndex = self.models.index(model) - 1

                for yearRange in self.yearRanges[1:]:
                    rangeIndex = self.yearRanges.index(yearRange) - 1
                    
                    if 0 == values[modelIndex, scenarioIndex, rangeIndex].count():
                        continue

                    if model not in historicalNames[0]:
                        historicalIndexMap[0].append(modelIndex)
                        historicalNames[0].append(model)
                    
                    if scenario not in historicalNames[1]:
                        historicalIndexMap[1].append(scenarioIndex)
                        historicalNames[1].append('historical')
                    
                    if yearRange not in historicalNames[2]:
                        historicalIndexMap[2].append(rangeIndex)
                        historicalNames[2].append(yearRange)
                    
                    for clim in climsSelected:
                        climIndex = theClims.index(clim)

                        if clim not in historicalNames[3]:
                            historicalIndexMap[3].append(climIndex)
                            historicalNames[3].append(clim)
                        
                        for latRange in latsSelected:
                            latIndex = self.latRanges.index(latRange) - 1
                        
                            if latRange not in historicalNames[4]:
                                historicalIndexMap[4].append(latIndex)
                                historicalNames[4].append(latRange)
                            
                            for lonRange in lonsSelected:
                                lonIndex = self.lonRanges.index(lonRange) - 1
                        
                                if lonRange not in historicalNames[5]:
                                    historicalIndexMap[5].append(lonIndex)
                                    historicalNames[5].append(lonRange)
                            
                                historicalIndices[0].append(modelIndex)
                                historicalIndices[1].append(scenarioIndex)
                                historicalIndices[2].append(rangeIndex)
                                historicalIndices[3].append(climIndex)        
                                historicalIndices[4].append(latIndex)
                                historicalIndices[5].append(lonIndex)

            historicalShape = (
                len(historicalNames[0]),
                1,
                1,
                len(historicalNames[3]),
                len(historicalNames[4]),
                len(historicalNames[5])
            )

            historicalValues = numpy.ma.masked_all(historicalShape, dtype = values.dtype)

            def mapIndices(mapList, indices):
                mappedIndices = list()

                for i, (mapper, index) in enumerate(zip(mapList, indices)):
                    outIndex = 0 if i in (1, 2) else mapper.index(index)

                    mappedIndices.append(outIndex)

                return tuple(mappedIndices)

            for inIndices in zip(*historicalIndices):
                outIndices = mapIndices(historicalIndexMap, inIndices)

                historicalValues[outIndices] = values[inIndices]

        names = list(names)

        tailsForTitle = list()

        if 'none' != spatialMeanSelected:
            picks = None

            if 'latitude' == spatialMeanSelected:
                picks = [ (4, 'lat', latsSelected) ]

            elif 'longitude' == spatialMeanSelected:
                picks = [ (5, 'lon', lonsSelected) ]

            else:
                picks = [ (4, 'lat', latsSelected), (5, 'lon', lonsSelected) ]

            for index, name, selected in picks:
                plotValues = plotValues.mean(axis = index, keepdims = True)

                selectionName = '%smean(%s)' % ((name, ','.join(selected)))

                tailsForTitle.append(selectionName)

                names[index] = [ '%smean' % (name,) ]

            if historicalValues is not None:
                for index, name, selected in picks:
                    historicalValues = historicalValues.mean(axis = index, keepdims = True)

        if historicalValues is not None:
            plotValues /= historicalValues

        xAxisIndex = self.xAxisOptions.index(xAxisSelected)
        
        xLabels = names.pop(xAxisIndex)

        names.append(xLabels)
        
        dimensions = [ x for x in range(0, plotValues.ndim) ]
        
        del dimensions[xAxisIndex]
        
        dimensions.append(xAxisIndex)
        
        plotValues = plotValues.transpose(dimensions)

        for dim in range(0, plotValues.ndim):
            axes = [ i for i in range(0, plotValues.ndim) ]

            del axes[dim]

            takes = 0 < plotValues.count(axis = tuple(axes))

            if False in takes:
                plotValues = plotValues.compress(takes, axis = dim)

                newNames = list()

                for index, name in enumerate(names[dim]):
                    if True == takes[index]:
                        newNames.append(name)

                names[dim] = newNames

        xLabels = names.pop(-1)

        numBarsInGroup = numpy.prod(plotValues.shape[0:-1])
        numGroups      = plotValues.shape[-1]
        
        plotValues = plotValues.reshape((numBarsInGroup, numGroups))
        
        titleElements = list()
        newNames      = list()

        namesShape = [ len(x) for x in names ]

        for index, size in enumerate(namesShape):
            if 1 < size:
                newNames.append(names[index])
            elif 1 == size:
                titleElements.append(names[index][0])
            else:
                print('size zero names list for index, size =', index, size)

        names = newNames

        titleElements += tailsForTitle

        titleElements = [ x for x in titleElements if x not in ('latmean', 'lonmean', 'modelmean') ]
        
        titleText = '<br>'.join(titleElements)

        title = '%s for %s' % ( yAxisSelected, titleText )

        barLabels = None

        if 0 < len(names):
            namesShape = [ len(x) for x in names ]

            nameIndices = numpy.indices(namesShape)
            nameIndices = nameIndices.reshape(len(names), nameIndices.size // len(names)).T

            barLabels = list()

            for indices in nameIndices[:]:
                barLabel = list() 

                for i, j in enumerate(indices):
                    barLabel.append(names[i][j])

                barLabels.append(' '.join(barLabel))

        takes = 0 < plotValues.count(axis = 1)

        if False in takes:
            plotValues = plotValues.compress(takes, axis = 0)

            newLabels = list()

            for index, label in enumerate(barLabels):
                if True == takes[index]:
                    newLabels.append(label)

            barLabels = newLabels

        takes = 0 < plotValues.count(axis = 0)

        if False in takes:
            plotValues = plotValues.compress(takes, axis = 1)

            newLabels = list()

            for index, label in enumerate(xLabels):
                if True == takes[index]:
                    newLabels.append(label)

            xLabels = newLabels

        numBarsInGroup = plotValues.shape[0]
        numGroups      = plotValues.shape[1]

        xTicks = [ i for i in range(0, numGroups) ]

        plotMax = 1.05 * plotValues.max()
        plotMin = 0.85 * plotValues.min()
        
        plotUnits = yUnitsSelected
        
        if 'values' != yAxisSelected:
            plotUnits = 'future/historical'
            
        makeLegend = True

        if barLabels is None:
            makeLegend = False

            barLabels = [ None ] * numBarsInGroup

        data = []

        for label, ys in zip(barLabels, plotValues[:]):
            data.append(go.Bar(y = ys, name = label))
        
        layout = go.Layout(barmode = 'group',
                           showlegend = makeLegend,
                           legend_orientation = 'h',
                           yaxis_title = plotUnits,
                           xaxis = { 'tickvals': xTicks, 'ticktext': xLabels, 'tickangle':45 },
                           title = title,
                           title_x = 0.5,
                           height = 800,
                           margin = { 'b': 40 })

        with self.figure.batch_update():
            self.figure.data   = []
            self.figure.layout = {}

            self.figure.add_traces(data)
            self.figure.layout = layout

            self.figure.update_yaxes(range = [plotMin, plotMax])

            if True == makeLegend:
                self.figure.update_layout(legend = { 'y': -0.1 })
