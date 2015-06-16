# The TableWidget #

One of the most important tools in the PyFlag GUI Framework is the Table Widget. This widget allows users to examine the contents of database tables in a powerful way - Allowing sorting, and filtering of data. From an analyst's point of view, the table widget allows endless avenues of interrogation of the data available. From the plugin developer's point of view, the table widget provides a simple and elegant way for presenting large quantities of data to users in a consistent way.

This tutorial covers both aspects of the Table Widget - first documenting how the widet can be used to assist in analysis. Finally the use of the table widget in a report is covered, providing vital documentation to plugin authors.

## Overview ##
The table widget has a similar appearance to the image below (Depending on the GUI chosen and the theme there may be some visual differences),

[table.jpg]

There are a number of important areas:

  1. Column Headers - Each column has a header with a descriptive name for that column. Some of the names consist of a number of words sepereted by spaces.

  1. One of the columns has an up or down arrow, as well as having a different background to the other column. This column is referred to as the sorted column. The data in the table is sorted on this column in either ascending order or descending order. Clicking on the sorted column will change the sort order for that column, while clicking on another column begin sorting by that column.

  1. The toolbar contains a number of functions relevant to the table widget:

  * The left and right arrows allow paging of the table data. The number of rows represented by the table could potentially be huge, therefore the table widget only displays a limited number of rows in each page allowing the user to browse between pages.

  * The next icon along allows the user to skip directly to a specified row number.

  * The filter icon allows users to filter the table.

## Table Filtering ##

Table filtering allows users to limit the rows displayed in the GUI to a few relevant rows to the course of the investigation. PyFlag does not force a specific methodology on the investigator. We prefer to allow analysts to explore their own filters and simply provide them with the tools to simplify this work.

By pressing the filter button, a popup dialog is presented allowing users to type a free form filter expression.

[table\_filter.jpg]

### Filter Expression Syntax ###
Although the filter expression is free form it must follow a simple syntax. The basic syntax is:

```
   "Column Name" operator Value
```

Where column name is the name of the column as presented in the GUI, the operator is one of the supported operators and the value will be operated on. If any of these values contain spaces, it is possible to delimit them with either double quotes " or single quotes '.

Filter expressions may be joined by the logical and, or, not keywords. These follow their usual precedence. Expressions may be delimited by use of round parentheses.

The GUI presents a selector of column names, and operators to assist users in typing in these often long winded values. The result, however, is usually very sensible. For example consider the following filter expression:

```
 Timestamp before '2006-11-01 10:10:00' and  ("IP Address" netmask "192.168.1.1/24" or "IP Address" = 192.168.10.1 )
```

The most fundamental idea behind the filter expression is that different columns have different types and therefore carry different operators. Clearly some operators simply can not be applied to certain columns because it does not make sense to do so. For example an "IP Address" column is of type IPAddrType. This type supports the netmask operator which parses the value as a CIDR netmask. Clearly it does not make sense for a Timestamp column to have a netmask operator, and attempting to use this operator on this column will generate an error.

This logic assures that the filter expression makes sense.

## Developing with the Table Widget ##
The following code snippet is a fairly complex table implementing most of the features available. It is taken from src/plugins/test.py:

```
        def foobar_cb(value):
            return "foo %s" % value

        result.table(
                         ## Can use keyword args
            elements = [ Timestamp(name = 'TimeStamp',
                                   column = 'time',
                                   ),

                         ## Or positional args
                         ColumnType('Data', 'data',
                            link = query_type(family=query['family'],
                                              report='FormTest',
                                              __target__='var1')),

                         ColumnType('Foobar', 'foobar', callback=foobar_cb),

                         ## Note that here we just need to specify the
                         ## field name in the table, the IPType will
                         ## automatically create the translated SQL.
                         IPType('IP Address', 'ip_addr'),
                         ],
            table = "TestTable",
            )
```

The table() method takes a number of keyword arguments the most important of those is the elements argument which must be filled. The elements argument is an array of objects which define each column. These objects must be instantiated from classes derived from ColumnType.

In the above example:

  1. The first element is a Timestamp() object. This object requires the column display name, and the column database name - these can be supplied as keyword args. The Timestamp class implements the "before" and "after" operators - this will allow users to use these on the Timestamp column.

  1. The next element is a simple ColumnType() object providing some of the basic operators. We also define a query object to be used as a link. When the table widget renders this column, the cell values will automatically be linked according to this object. The value of target will be replaced by the respective cell value in the link.

  1. The next column (Foobar) implements a callback for its rendering. When the table widget renders this column, all values for each cell will be sent to the specified callback, with the result rendered. The callback may simply return a string as is the case here, or it may return any UI object (e.g. an image, link or whatever).

  1. Finally the last element is defined as an IP Address. This definition will automatically declare the netmask operator. In addition the cells will be rendered in dot decimal notation, while the database will be storing the data as an int (i.e. there will be an automatic inet\_ntoa() called on the data). Despite this, the IPType class ensures that comparison operators are applied.

The end result is that the table is defined with a minimum amount of code. This makes it very readable because columns are described in high level terms, and automatically apply sane behaviour depending on the column meaning. The elements also influence the filter parser, allowing it to ensure consistancy.