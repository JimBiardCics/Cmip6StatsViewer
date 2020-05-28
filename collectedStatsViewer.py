import plotly.graph_objs as go
import ipywidgets as widgets

import netCDF4
import numpy
import os
import sys
import warnings


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
        # Build copies of the multi-selection inputs.
        #
        modelsSelected    = list(modelsSelected)
        scenariosSelected = list(scenariosSelected)
        climsSelected     = list(climsSelected)
        rangesSelected    = list(rangesSelected)
        latsSelected      = list(latsSelected)
        lonsSelected      = list(lonsSelected)

        # Build the seasonal or monthly data selection.
        #
        if 'all seasons' == climsSelected[0]:
            climsSelected = list(self.seasons)
            theClims      = list(self.seasons)
            values        = self.seasonalValues.copy()
            stdevs        = self.seasonalStdevs.copy()

        elif 'all months' == climsSelected[0]:
            climsSelected = list(self.months)
            theClims      = list(self.months)
            values        = self.monthlyValues.copy()
            stdevs        = self.monthlyStdevs.copy()

        elif set(climsSelected) <= set(self.seasons):
            theClims = list(self.seasons)
            values   = self.seasonalValues.copy()
            stdevs   = self.seasonalStdevs.copy()

        elif set(climsSelected) <= set(self.months):
            theClims = list(self.months)
            values   = self.monthlyValues.copy()
            stdevs   = self.monthlyStdevs.copy()

        else:
            warnings.warn('Selecting a mix of months and seasons is forbidden.')

            return

        # Scale the values.
        #
        values = values * self.yUnitsFactors[yUnitsSelected]

        # Get the historical values.
        #
        index = self.scenarios[1:].index('historical')

        historicalValues = values[:,index:index+1]

        # Remove the non-historical year sets from the historical values.
        # (There is only one historical year per model.)
        #
        historicalShape = list(historicalValues.shape)

        numSets = numpy.prod(historicalShape[0:3])
        numInSet = numpy.prod(historicalShape[3:])

        historicalValues = historicalValues.reshape((numSets, numInSet))

        takes = 0 < historicalValues.count(axis = 1)

        historicalValues = historicalValues.compress(takes, axis = 0)

        historicalShape[2] = 1

        historicalValues = historicalValues.reshape(historicalShape)

        # Get the model, scenario, year range, latitude, and longitude
        # selections.
        #
        if 'all' == modelsSelected[0]:
            modelsSelected = list(self.models[1:])

        if 'all' == scenariosSelected[0]:
            scenariosSelected = list(self.scenarios[1:])
        
        if 'all' == rangesSelected[0]:
            rangesSelected = list(self.yearRanges[1:])
        
        if 'all' == latsSelected[0]:
            latsSelected = list(self.latRanges[1:])
        
        if 'all' == lonsSelected[0]:
            lonsSelected = list(self.lonRanges[1:])
        
        if 'values' != yAxisSelected:
            try:
                scenariosSelected.remove('historical')
            except:
                pass

        # Make a list to hold names that will get shifted to the title for
        # various reasons.
        #
        tailsForTitle = list()

        # Get lists of all the names and lists of the indices for the selected
        # names.
        #
        names = [
            list(self.models[1:]),
            list(self.scenarios[1:]),
            list(self.yearRanges[1:]),
            list(theClims),
            list(self.latRanges[1:]),
            list(self.lonRanges[1:])
        ]

        selectionIndices = [
            [ names[0].index(x) for x in modelsSelected ],
            [ names[1].index(x) for x in scenariosSelected ],
            [ names[2].index(x) for x in rangesSelected ],
            [ names[3].index(x) for x in climsSelected ],
            [ names[4].index(x) for x in latsSelected ],
            [ names[5].index(x) for x in lonsSelected ]
        ]

        # Subset the values and historical values by the selections.
        #
        selectionMesh = numpy.meshgrid(*selectionIndices, indexing = 'ij', sparse = True)

        values = values[tuple(selectionMesh)]

        selectionMesh[1] = 0
        selectionMesh[2] = 0

        historicalValues = historicalValues[tuple(selectionMesh)]

        # If the selection is empty, report it and return.
        #
        if 0 == values.count():
            warnings.warn('Nothing to display.')

            return

        # If some spatial mean has been selected, take it. Adjust the name
        # lists and selection index lists appropriately. Save the detailed
        # spatial labeling in the title tails list.
        #
        if 'none' != spatialMeanSelected:
            picks = None

            if 'latitude' == spatialMeanSelected:
                picks = [ (4, 'lat', latsSelected) ]

            elif 'longitude' == spatialMeanSelected:
                picks = [ (5, 'lon', lonsSelected) ]

            else:
                picks = [ (4, 'lat', latsSelected), (5, 'lon', lonsSelected) ]

            for index, name, selected in picks:
                values = values.mean(axis = index, keepdims = True)

                historicalValues = historicalValues.mean(axis = index, keepdims = True)

                selectionName = '%smean(%s)' % ((name, ','.join(selected)))

                tailsForTitle.append(selectionName)

                names[index] = [ '%smean' % (name,) ]

                selectionIndices[index] = 0

        # If ratios were selected, take the ratio.
        #
        if 'values' != yAxisSelected:
            values /= historicalValues

        # Rotate the lists and the values array to put the selected x axis
        # dimension last, then flatten all but the last dimension of the array.
        #
        xAxisIndex = self.xAxisOptions.index(xAxisSelected)
        
        xLabels = names.pop(xAxisIndex)

        xLabelIndices = numpy.array(selectionIndices.pop(xAxisIndex))

        dimensions = [ x for x in range(0, values.ndim) ]
        
        del dimensions[xAxisIndex]
        
        dimensions.append(xAxisIndex)
        
        values = values.transpose(dimensions)

        values = values.reshape((values.size // values.shape[-1], values.shape[-1]))

        # Create a list of tuples of indices into the names for building the
        # bar labels, then turn it into an array.
        #
        selectionMesh = numpy.meshgrid(*selectionIndices, indexing = 'ij')

        selectionMesh = [ x.ravel() for x in selectionMesh ]

        indexList = [ x for x in zip(*selectionMesh) ]

        barLabelIndices = numpy.array(indexList)

        # Remove any empty rows or columns from the values array. Remove the
        # corresponding elements from the bar label indices and x label indices
        # arrays.
        #
        takes = 0 < values.count(axis = 0)

        values          = values.compress(takes, axis = 1)
        xLabelIndices   = xLabelIndices.compress(takes)

        takes = 0 < values.count(axis = 1)

        values  = values.compress(takes, axis = 0)
        barLabelIndices = barLabelIndices.compress(takes, axis = 0)

        numBarsInGroup = values.shape[0]
        numGroups      = values.shape[1]

        # Find all constant name elements in the bar labels.
        #
        constantLabelIndices = numpy.full((5,), -1, dtype = int)

        for col, sub in enumerate(barLabelIndices.T):
            unique = numpy.unique(sub)

            if 1 == unique.size:
                constantLabelIndices[col] = unique[0]

        # Remove the columns that are constant and add the elements to the title elements.
        #
        takes = -1 == constantLabelIndices

        barLabelIndices = barLabelIndices.compress(takes, axis = 1)

        titleElements = list()
        newNames      = list()

        for row, col in enumerate(constantLabelIndices):
            if -1 == col:
                newNames.append(names[row])
            else:
                titleElements.append(names[row][col])
                
        names = newNames

        # Build the graph title.
        #
        titleElements += tailsForTitle

        titleElements = [ x for x in titleElements if x not in ('latmean', 'lonmean') ]
        
        titleText = '<br>'.join(titleElements)

        title = '%s for %s' % ( yAxisSelected, titleText )

        # Build the bar labels.
        #
        barLabels = None
        makeLegend = True

        if 2 > len(barLabelIndices):
            makeLegend = False

            barLabels = [ None ] * numBarsInGroup
        else:
            barLabels = list()

            for indexList in barLabelIndices:
                nameList = [ names[i][j] for i, j in enumerate(indexList) ]

                barLabels.append(' '.join(nameList))

        # Build the x axis labels and locations.
        #
        xLabels = [ xLabels[i] for i in xLabelIndices ]
        xTicks  = [ i for i in range(0, numGroups) ]

        plotMax = 1.05 * values.max()
        plotMin = 0.85 * values.min()
        
        plotUnits = yUnitsSelected
        
        if 'values' != yAxisSelected:
            plotUnits = 'future/historical'
            
        data = list()

        for label, ys in zip(barLabels, values[:]):
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
